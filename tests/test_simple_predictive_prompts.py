"""Approved concise prompt contracts; synthetic checks do not prove task benefit."""
from test_predictive_memory_read import Agent, Script, call, response, run
from memory_agent.memory.read_context_predictive_memory_agent import (
    BANK_TOOLS, PHASE1_SYSTEM)
from memory_agent.memory.predictive_memory_agent import PHASE2_SYSTEM


def test_p1_keeps_approved_forecast_goal_and_tools():
    assert PHASE1_SYSTEM == '''You are a memory manager for the task agent.

Based on the task description and the task agent's trajectory, first anticipate the problems the task agent may encounter or the decisions it may need to make over the next 10 turns, and what information it will need then; organize and save that information accordingly.

Before using memory tools, briefly state in ordinary reply text the upcoming problems or decisions you anticipate and the information you plan to preserve for them. Give a concise public summary, not private reasoning. No special format is needed.

Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge".'''
    assert [t['function']['name'] for t in BANK_TOOLS] == ['memory_add', 'memory_read']
    assert BANK_TOOLS[0]['function']['description'] == 'Save information in the knowledge memory bank.'


def test_p2_keeps_approved_selective_reminder_contract():
    assert PHASE2_SYSTEM == '''You help the task agent complete its task by reminding it of relevant information from memory at appropriate times.

Review the memory bank alongside the task requirements and the agent's recent trajectory, and decide whether any information can help its current work. You may synthesize information, identify connections, and offer grounded inferences or suggestions; preserve the information's original uncertainty when expressing them.

Default to no intervention. Do not intervene if no reminder is needed now, or if the relevant information is already visible in the recent trajectory and the agent's actions indicate that it has taken it into account. Do not take over the task agent's work.

If a reminder is needed, write:
<context_for_action>
Relevant information to bring to the agent's attention.
</context_for_action>

Otherwise, write:
<no_intervention/>'''


def test_prompts_and_uncertain_note_reach_actual_phases_without_new_tools():
    note = 'Possibly helpful next: check the layout; it has not been confirmed.'
    class ReminderScript(Script):
        async def call(self, **kwargs):
            result = await super().call(**kwargs)
            if not kwargs.get('tools'):
                return response(content='<context_for_action>' + note + '</context_for_action>')
            return result
    llm = ReminderScript(response(call('memory_add', {'content': note})))
    agent = Agent(llm=llm)
    result = run(agent)
    assert llm.calls[0]['system'] == PHASE1_SYSTEM
    assert llm.calls[1]['system'] == PHASE2_SYSTEM
    assert note in llm.calls[1]['prompt']
    assert 'tools' not in llm.calls[1]
    assert result.should_inject
    assert agent._parse_phase2_response('<no_intervention/>') is None
