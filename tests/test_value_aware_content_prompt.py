"""Exact prompt and mock request checks; no model or Task execution."""
from memory_agent.memory.reminder_tool_memory_agent import (
    REMINDER_TOOL_SYSTEM, ReminderToolMemoryAgent,
)
from test_predictive_memory_read import Script, run
from test_remind_first_loop import add, done
from test_predictive_tool_recovery import block_network  # noqa: F401


EXPECTED_SYSTEM = '''You are the task agent's information manager.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the newly observed execution trajectory.

## Tools

- memory_read: Read information saved in the knowledge bank. Set bank_id to "knowledge" when calling it.
- send_reminder: Record a reminder for the task agent. All reminders successfully recorded during a wake are delivered in call order after that wake completes normally; later reminders do not replace earlier ones.
- memory_add: Save information in the knowledge bank.

Work in the following order:

1. Judge and remind. Use memory_read to review the knowledge bank. Consider it alongside the original task and the newly observed execution trajectory. When the task agent's work shows a disconnect between earlier and later steps, use send_reminder to remind it.

2. Predict and save. You must first predict which information from the original task and the newly observed execution trajectory will still be useful to the task agent's later work after eight more task turns. Based on this prediction, use memory_add to organize and save the selected information in the knowledge bank.
'''


def test_exact_candidate_prompt_and_horizon():
    assert REMINDER_TOOL_SYSTEM == EXPECTED_SYSTEM
    assert REMINDER_TOOL_SYSTEM.count('eight more task turns') == 1
    assert 'a disconnect between earlier and later steps' in REMINDER_TOOL_SYSTEM
    assert 'You must first predict' in REMINDER_TOOL_SYSTEM
    assert 'Based on this prediction' in REMINDER_TOOL_SYSTEM


def test_actual_mock_requests_do_not_add_a_forecast_explanation_requirement():
    agent = ReminderToolMemoryAgent(llm=Script(add(content=''), done()))
    result = run(agent)
    assert agent.llm.calls[0]['system'] == REMINDER_TOOL_SYSTEM
    tool = next(t['function'] for t in agent.llm.calls[0]['tools']
                if t['function']['name'] == 'send_reminder')
    assert tool['description'].startswith('Record a reminder for the task agent')
    assert tool['parameters']['properties']['content']['description'].startswith(
        'The content of the reminder for the task agent.')
    assert tool['parameters']['required'] == ['content']
    assert tool['parameters']['additionalProperties'] is False
    assert agent.llm.calls[1]['system'] == REMINDER_TOOL_SYSTEM
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
    assert all(req['system'] == REMINDER_TOOL_SYSTEM for req in agent.llm.calls)
    assert receipts(agent.llm.calls[1])[0]['success']
    assert receipts(agent.llm.calls[3])[-1]['success']
