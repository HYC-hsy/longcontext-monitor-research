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
    "2. Predict and save. Pieces of information affect one another's value. "
    "Organize information only to the extent supported by the available information. "
    "After completing the "
    "reminder decision, based on the task description, the task agent's trajectory, "
    "and the judgment and reminder decision you have just made, you must predict "
    "which information received this time will still be worth presenting to the "
    "task agent to support subsequent task work after the task has progressed for "
    "another eight turns, and predict what content to produce when organizing that "
    "information to make it most valuable for subsequent task work, then save it "
    "in the knowledge bank.\n"
)


def test_only_step_two_changes_and_forecast_horizon_is_not_repeated():
    prefix, step = REMINDER_TOOL_SYSTEM.split('2. ', 1)
    # Prefix fingerprint from pinned parent 381f0658, including step one.
    assert hashlib.sha256(prefix.encode()).hexdigest() == (
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
