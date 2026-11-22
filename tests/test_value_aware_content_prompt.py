"""Exact prompt and mock request checks; no model or Task execution."""
from memory_agent.memory.reminder_tool_memory_agent import (
    REMINDER_TOOL_SYSTEM, ReminderToolMemoryAgent,
)
from memory_agent.memory.read_context_predictive_memory_agent import PUBLIC_FORECAST_REMINDER
from test_predictive_memory_read import Script, run
from test_remind_first_loop import add, done
from test_predictive_tool_recovery import block_network  # noqa: F401


READ_BEFORE_REMINDER = '- Before each call to send_reminder, first call memory_read to retrieve information from the knowledge bank.\n'
EXPECTED_SYSTEM = '''You are the task agent's "selective attention" module. Your role is to save information from the task that will be valuable for later work and, when the task agent's work shows a disconnect between earlier and later steps, to present the relevant material from both, bringing overlooked information back into consideration so it can go back and check the material and decide for itself what to do next.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

## Tools

- memory_add: Save information in the knowledge bank.
- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.
- send_reminder: Record material and any necessary context to present to the task agent. Everything successfully recorded during a wake is delivered in call order after that wake completes normally; later content does not replace earlier content.

## Action Principles

- Before calling memory_add, briefly explain which information you selected and why. Before calling send_reminder, briefly explain which material you selected and why it needs to be presented now.
- Before each call to send_reminder, first call memory_read to retrieve information from the knowledge bank.

Please manage task information in the following order:

1. Judge and present material. Use memory_read to review information previously saved in the knowledge bank, and consider it alongside the newly observed execution trajectory. When the task agent's work shows a disconnect between earlier and later steps, use send_reminder to present the relevant material from both, together with any necessary context, so the task agent can go back and check it and decide for itself what to do next.

2. Predict and save. After making the decision above, you must predict which information from the original task description and the newly observed execution trajectory will still be worth presenting to the task agent to support subsequent work after the task has progressed for another eight turns. Use memory_add to organize the selected information and any necessary context into material that can be revisited later, and save it in the knowledge bank. Even when the task agent can no longer see the original records, it should be able to understand what the information meant at the time and use it to make further judgments.
'''


def test_exact_candidate_prompt_and_horizon():
    assert REMINDER_TOOL_SYSTEM == EXPECTED_SYSTEM
    assert REMINDER_TOOL_SYSTEM.count('eight turns') == 1
    assert REMINDER_TOOL_SYSTEM.count(READ_BEFORE_REMINDER) == 1


def test_actual_mock_requests_and_original_soft_reminder():
    assert PUBLIC_FORECAST_REMINDER == (
        'Please use one or two sentences to explain which information you have selected '
        'and why you judge that it will still be worth presenting to the task agent to '
        'support subsequent work after the task has progressed for another eight turns.')
    agent = ReminderToolMemoryAgent(llm=Script(add(content=''), done()))
    result = run(agent)
    assert agent.llm.calls[0]['system'] == REMINDER_TOOL_SYSTEM
    tool = next(t['function'] for t in agent.llm.calls[0]['tools']
                if t['function']['name'] == 'send_reminder')
    assert tool['description'].startswith('Record material and any necessary context')
    assert tool['parameters']['properties']['content']['description'].startswith(
        'The complete material and necessary context')
    assert tool['parameters']['required'] == ['content']
    assert tool['parameters']['additionalProperties'] is False
    assert agent.llm.calls[1]['system'] == REMINDER_TOOL_SYSTEM + '\n\n' + PUBLIC_FORECAST_REMINDER
    assert result.termination == 'wake_no_tool'
    assert not result.should_inject


def test_each_reminder_can_read_first_and_receive_current_bank():
    from test_remind_first_loop import read
    from test_reminder_tool_loop import remind
    from test_predictive_memory_read import receipts
    agent = ReminderToolMemoryAgent(llm=Script(
        read('r1'), remind('first', 's1'), read('r2'), remind('second', 's2'), done()))
    result = run(agent)
    assert [op.action for op in result.operations] == [
        'read', 'send_reminder', 'read', 'send_reminder']
    assert result.context_for_action == 'first\n\nsecond'
    assert all(READ_BEFORE_REMINDER in req['system'] for req in agent.llm.calls)
    assert receipts(agent.llm.calls[1])[0]['success']
    assert receipts(agent.llm.calls[3])[-1]['success']
