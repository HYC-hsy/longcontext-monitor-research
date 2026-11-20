"""Exact prompt and mock request checks; no model or Task execution."""
import hashlib

from memory_agent.memory.reminder_tool_memory_agent import (
    REMINDER_TOOL_SYSTEM, ReminderToolMemoryAgent,
)
from memory_agent.memory.read_context_predictive_memory_agent import PUBLIC_FORECAST_REMINDER
from test_predictive_memory_read import Script, run
from test_remind_first_loop import add, done
from test_predictive_tool_recovery import block_network  # noqa: F401


EXPECTED_STEP = (
    "2. Predict and save. Pieces of information affect one another's value. After completing "
    "the reminder decision, based on the task description, the task agent's execution "
    'trajectory, and the judgment and reminder decision you have just made, you must predict '
    'which fragments of the original information received this time will still be worth '
    'presenting to the task agent to support subsequent task work after the task has '
    'progressed for another eight turns. Organize and summarize the selected fragments '
    'together with the context needed to understand them, and save them in the knowledge bank as memories whose origins are clear and that can be revised in light of new information.\n'
)
SAVE_FROM_ORIGINAL_FRAGMENTS = (
    '- When saving, use the selected original information fragments as material to '
    'organize and summarize, preserving their original meaning and current state, '
    'as well as the context needed to understand and use them later.'
)
ORIGINAL_SAVE_RULE = (
    '- When saving, fully retain the content needed to understand and use the selected '
    'information later.'
)
READ_BEFORE_REMINDER = '- Before each call to send_reminder, first call memory_read to retrieve information from the knowledge bank.\n'

def test_only_approved_prompt_parts_change_and_horizon_is_not_repeated():
    prefix, step = REMINDER_TOOL_SYSTEM.split('2. ', 1)
    assert prefix.count(READ_BEFORE_REMINDER) == 1
    assert prefix.count("1. Judge and decide the reminder. Use memory_read to review information previously saved in the knowledge bank. Consider the newly observed execution trajectory and use send_reminder to remind the task agent when its work shows a disconnect between earlier and later steps.") == 1
    # Undo only the approved action-rule additions to recover the original prefix.
    assert prefix.count('one or two sentences') == 1
    assert prefix.count(SAVE_FROM_ORIGINAL_FRAGMENTS) == 1
    baseline_prefix = prefix.replace("1. Judge and decide the reminder. Use memory_read to review information previously saved in the knowledge bank. Consider the newly observed execution trajectory and use send_reminder to remind the task agent when its work shows a disconnect between earlier and later steps.", "1. Judge and decide the reminder. You must use memory_read to carefully review the existing knowledge bank. After receiving its result, consider the task agent's execution trajectory. You must judge which information in the knowledge bank, as the task progresses, has become valuable or remains valuable for the task agent's current or upcoming work, and accordingly decide whether to remind the task agent and what to remind it of. If a reminder is needed, call send_reminder with its content. Otherwise, do not call it.").replace(SAVE_FROM_ORIGINAL_FRAGMENTS, ORIGINAL_SAVE_RULE).replace(
        READ_BEFORE_REMINDER, '').replace(
        '- Before each tool call, you must use one or two sentences to explain your '
        'judgment, the available information on which it is based, and the extent to '
        'which that information supports it. When calling memory_add, also state which '
        'information you have selected.',
        '- Before each tool call, briefly explain your judgment; when calling memory_add, '
        'state which information you have selected.')
    assert hashlib.sha256(baseline_prefix.encode()).hexdigest() == (
        'd29718385b7890d0bdf83736a94da6378cd005d7fa23b4599c0d2779c196c048')
    assert '2. ' + step == EXPECTED_STEP
    assert REMINDER_TOOL_SYSTEM.count('eight turns') == 1


def test_actual_mock_requests_and_original_soft_reminder():
    assert PUBLIC_FORECAST_REMINDER == (
        'Please use one or two sentences to explain which information you have selected '
        'and why you judge that it will still be worth presenting to the task agent to '
        'support subsequent work after the task has progressed for another eight turns.')
    agent = ReminderToolMemoryAgent(llm=Script(add(content=''), done()))
    result = run(agent)
    assert agent.llm.calls[0]['system'] == REMINDER_TOOL_SYSTEM
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


def test_selected_fragments_preserve_meaning_state_and_context():
    assert SAVE_FROM_ORIGINAL_FRAGMENTS in REMINDER_TOOL_SYSTEM
    assert 'predict how to organize' not in REMINDER_TOOL_SYSTEM
    assert 'Based on these predictions' not in REMINDER_TOOL_SYSTEM
    assert REMINDER_TOOL_SYSTEM.rstrip().endswith(
        'Organize and summarize the selected fragments together with the context needed '
        'to understand them, and save them in the knowledge bank as memories whose origins are clear and that can be revised in light of new information.')
    assert 'Organize information only to the extent supported' not in REMINDER_TOOL_SYSTEM
