"""Reminder newly or still valuable information judgment; no runtime/lifecycle changes."""
import hashlib
from pathlib import Path
from memory_agent.memory import read_context_predictive_memory_agent as module
from test_remind_first_loop import make, read, decision, done, run

OLD = "After receiving its result, based on the task agent's current and upcoming work, decide whether to remind it of information in that bank."
NEW = "After receiving its result, consider the conversation context and the task agent's execution trajectory. You must judge which information in the knowledge bank, as the task progresses, has become valuable or remains valuable for the task agent's current or upcoming work, and accordingly decide whether to remind the task agent and what to remind it of. Before expressing the reminder decision, briefly explain your judgment."
SYSTEM_SHA256 = 'b5dfae02b238d94745743798444c3ef5e5e8d128aca8806ec6a6340faa7bc451'


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
    parent_sentence = "After receiving its result, consider the conversation context and the task agent's execution trajectory. You must judge which information in the knowledge bank is worth presenting to the task agent for its current or upcoming work, and accordingly decide whether to remind the task agent and what to remind it of. Before expressing the reminder decision, briefly explain your judgment."
    parent = module.REMIND_FIRST_SYSTEM.replace(NEW, parent_sentence).replace(
        '1. Judge and decide the reminder.', '1. Recall and decide the reminder.')
    assert hashlib.sha256(parent.encode()).hexdigest() == '249d201c0e01483764266569f2f8faceb10a49e7ce50653974eb3c0c517e9646'


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


def test_reminder_judges_both_new_and_retained_value():
    assert '1. Judge and decide the reminder.' in module.REMIND_FIRST_SYSTEM
    assert 'has become valuable or remains valuable' in module.REMIND_FIRST_SYSTEM
    assert 'Use memory_read to read the existing knowledge bank.' in module.REMIND_FIRST_SYSTEM
