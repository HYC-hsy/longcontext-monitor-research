"""Reminder newly or still valuable information judgment; no runtime/lifecycle changes."""
import hashlib
from pathlib import Path
from memory_agent.memory import read_context_predictive_memory_agent as module
from test_remind_first_loop import make, read, decision, done, run

OLD = "After receiving its result, based on the task agent's current and upcoming work, decide whether to remind it of information in that bank."
NEW = "After receiving its result, consider the task agent's execution trajectory. You must judge which information in the knowledge bank, as the task progresses, has become valuable or remains valuable for the task agent's current or upcoming work, and accordingly decide whether to remind the task agent and what to remind it of."
SYSTEM_SHA256 = '25d004ef5898c5814926aff3b862ceeb34394fd3ccccde158f214eae89aad4e5'
PARENT_SYSTEM = 'You are the task agent\'s information manager. Some information that appears during task execution remains valuable much later in the task, while other information only becomes valuable then. Your role is first to draw on previously organized information to decide whether to remind the task agent, then to predict and save newly received information that will be valuable for later work, helping it use existing information to complete the task.\n\nThe <task_description> tags contain the task agent\'s original task, and the <task_trajectory> tags contain the task agent\'s newly observed execution trajectory.\n\nCarry out these steps in this same conversation:\n\n1. Judge and decide the reminder. Use memory_read to read the existing knowledge bank. After receiving its result, consider the conversation context and the task agent\'s execution trajectory. You must judge which information in the knowledge bank, as the task progresses, has become valuable or remains valuable for the task agent\'s current or upcoming work, and accordingly decide whether to remind the task agent and what to remind it of. Before expressing the reminder decision, briefly explain your judgment. Express the reminder decision with one of:\n<context_for_action>\nInformation to remind the task agent of.\n</context_for_action>\n<no_intervention/>\n\n2. Predict and save. Based on the task description, the task agent\'s trajectory, and the judgment you have just made, you must predict which information received this time will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns, and organize and save that information in the knowledge bank. When saving, fully retain the content needed to understand and use the selected information later. Before saving, briefly state which information you have selected.\n\n## Tools\n- memory_add: Save information in the knowledge bank.\n- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.\n'


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


def test_approved_action_principles_and_order():
    prompt = module.REMIND_FIRST_SYSTEM
    assert prompt.index('## Tools') < prompt.index('## Action Principles') < prompt.index('1. Judge') < prompt.index('2. Predict')
    assert 'Before expressing the reminder decision, briefly explain your judgment.' in prompt
    assert 'Before calling memory_add, briefly state which information you have selected.' in prompt
    assert 'in this same conversation' not in prompt
    assert hashlib.sha256(PARENT_SYSTEM.encode()).hexdigest() == 'b5dfae02b238d94745743798444c3ef5e5e8d128aca8806ec6a6340faa7bc451'


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
    assert 'You must use memory_read to carefully review the existing knowledge bank.' in module.REMIND_FIRST_SYSTEM
