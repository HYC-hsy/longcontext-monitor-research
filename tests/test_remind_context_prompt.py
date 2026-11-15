"""Mandatory reminder judgment explanation; no runtime/lifecycle changes."""
import hashlib
from pathlib import Path
from memory_agent.memory import read_context_predictive_memory_agent as module
from test_remind_first_loop import make, read, decision, done, run

OLD = "After receiving its result, based on the task agent's current and upcoming work, decide whether to remind it of information in that bank."
NEW = "After receiving its result, consider the conversation context and compare relevant information in the knowledge bank with the task agent's current and upcoming work. You must judge whether to remind the task agent and what to remind it of, and briefly explain your judgment before expressing the reminder decision."
SYSTEM_SHA256 = '5b8890affc47f7abdb3a32dec5a5c075ed186e84a231adedc4c892d8d6c411c6'


def test_approved_system_has_complete_save_guidance_and_same_reminder():
    assert module.REMIND_FIRST_SYSTEM.count(NEW) == 1
    assert OLD not in module.REMIND_FIRST_SYSTEM
    assert hashlib.sha256(module.REMIND_FIRST_SYSTEM.encode()).hexdigest() == SYSTEM_SHA256


def test_context_and_bank_wording_reaches_all_requests_and_initialization_is_unified():
    agent = make(read(), decision(), done('Nothing to save.'))
    result = run(agent)
    assert not result.should_inject
    assert [item['stage'] for item in result.loop_rounds] == ['remind', 'remind', 'organize']
    assert all(NEW in request['system'] for request in agent.llm.calls)
    assert all(OLD not in request['system'] for request in agent.llm.calls)
    assert '(empty)' in result.operations[0].content


def test_only_reminder_sentence_changed_from_parent_system():
    parent_sentence = "After receiving its result, consider the conversation context and compare relevant information in the knowledge bank with the task agent's current and upcoming work to decide whether to remind the task agent, and what to remind it of."
    parent = module.REMIND_FIRST_SYSTEM.replace(NEW, parent_sentence)
    assert hashlib.sha256(parent.encode()).hexdigest() == '0e397e323abb83a9b479a0be802dc0a9ef771dd3a06bb765dd063069a867b169'


def test_explanation_before_no_intervention_is_accepted_without_extra_round():
    agent = make(read(), done('The current work agrees with the stored requirements. <no_intervention/>'), done('Nothing to save.'))
    result = run(agent)
    assert not result.should_inject
    assert [item['stage'] for item in result.loop_rounds] == ['remind', 'remind', 'organize']


def test_explanation_before_intervention_is_not_injected_as_reminder():
    agent = make(read(), done('The current output conflicts with the stored requirement. <context_for_action>Keep three dimensions.</context_for_action>'), done('Nothing to save.'))
    result = run(agent)
    assert result.should_inject
    assert result.context_for_action == 'Keep three dimensions.'
    assert [item['stage'] for item in result.loop_rounds] == ['remind', 'remind', 'organize']
