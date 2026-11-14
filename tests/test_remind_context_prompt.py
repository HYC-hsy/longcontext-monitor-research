"""Approved context-and-bank wording; no runtime/lifecycle changes."""
import hashlib
from pathlib import Path
from memory_agent.memory import read_context_predictive_memory_agent as module
from test_remind_first_loop import make, read, decision, done, run

OLD = "After receiving its result, based on the task agent's current and upcoming work, decide whether to remind it of information in that bank."
NEW = "After receiving its result, consider the conversation context and compare relevant information in the knowledge bank with the task agent's current and upcoming work to decide whether to remind the task agent, and what to remind it of."
PARENT_SYSTEM_SHA256 = '0e397e323abb83a9b479a0be802dc0a9ef771dd3a06bb765dd063069a867b169'


def test_approved_information_manager_prompt():
    assert module.REMIND_FIRST_SYSTEM.count(NEW) == 1
    assert OLD not in module.REMIND_FIRST_SYSTEM
    assert hashlib.sha256(module.REMIND_FIRST_SYSTEM.encode()).hexdigest() == PARENT_SYSTEM_SHA256


def test_context_and_bank_wording_reaches_all_requests_and_initialization_is_unified():
    agent = make(read(), decision(), done('Nothing to save.'))
    result = run(agent)
    assert not result.should_inject
    assert all('stage' not in item for item in result.loop_rounds)
    assert all(NEW in request['system'] for request in agent.llm.calls)
    assert all(OLD not in request['system'] for request in agent.llm.calls)
    assert '(empty)' in result.operations[0].content


def test_old_information_reminder_precedes_new_information_forecast():
    prompt = module.REMIND_FIRST_SYSTEM
    assert "You are the task agent's information manager." in prompt
    assert "first to draw on previously organized information" in prompt
    assert "then to predict and save newly received information" in prompt
    assert prompt.index("1. Recall and decide the reminder.") < prompt.index("2. Predict and save.")
    assert "the judgment you have just made, you must predict" in prompt
