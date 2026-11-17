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
    'which information received this time will still be worth presenting to the task agent to'
    ' support subsequent task work after the task has progressed for another eight turns. For'
    ' the selected information, faithfully organize its content and current state and save it'
    ' in the knowledge bank.\n'
)
READ_BEFORE_REMINDER = '- Before each call to send_reminder, first call memory_read to retrieve information from the knowledge bank.\n'

def test_only_approved_prompt_parts_change_and_horizon_is_not_repeated():
    prefix, step = REMINDER_TOOL_SYSTEM.split('2. ', 1)
    assert prefix.count(READ_BEFORE_REMINDER) == 1
    # Undo only the approved action-rule additions to recover the original prefix.
    assert prefix.count('and the extent to which the available information supports it') == 1
    baseline_prefix = prefix.replace(READ_BEFORE_REMINDER, '').replace(
        'your judgment and the extent to which the available information supports it;',
        'your judgment;')
    assert hashlib.sha256(baseline_prefix.encode()).hexdigest() == (
        'd29718385b7890d0bdf83736a94da6378cd005d7fa23b4599c0d2779c196c048')
    assert '2. ' + step == EXPECTED_STEP
    assert REMINDER_TOOL_SYSTEM.count('eight turns') == 1


def test_actual_mock_requests_and_original_soft_reminder():
    assert PUBLIC_FORECAST_REMINDER == (
        'Briefly state which information you have selected that you predict will '
        'still be worth presenting to the task agent to support subsequent task '
        'work after the task has progressed for another eight turns.')
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


def test_selected_information_is_faithful_not_an_extra_organization_forecast():
    assert 'For the selected information, faithfully organize its content and current state' in REMINDER_TOOL_SYSTEM
    assert 'predict how to organize' not in REMINDER_TOOL_SYSTEM
    assert 'Based on these predictions' not in REMINDER_TOOL_SYSTEM
    assert REMINDER_TOOL_SYSTEM.rstrip().endswith(
        'For the selected information, faithfully organize its content and current state and save it in the knowledge bank.')
    assert 'Organize information only to the extent supported' not in REMINDER_TOOL_SYSTEM
