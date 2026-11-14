"""Prompt-guided tools/reminders: no stage gates; synthetic providers only."""
import asyncio
import json
from pathlib import Path

import pytest
from test_predictive_memory_read import Script, call, response, run, receipts
from test_predictive_tool_recovery import block_network  # noqa: F401
from memory_agent.memory.read_context_predictive_memory_agent import (
    RemindFirstMemoryAgent as Agent, REMIND_FIRST_SYSTEM, is_organize_completion)
from memory_agent.memory.ga_context_history import GAHistoryIntegrityError, provider_history

@pytest.fixture(autouse=True)
def offline_model_metadata(monkeypatch):
    monkeypatch.setenv('LITELLM_LOCAL_MODEL_COST_MAP', 'True')

def read(ident='r', content='Read old bank.'):
    return response(call('memory_read', {'bank_id': 'knowledge'}, ident), content=content)

def add(value='new', ident='a', content='Selected future information.'):
    return response(call('memory_add', {'content': value}, ident), content=content)

def decision(body=None):
    return response(content='<no_intervention/>' if body is None else
                    f'<context_for_action>{body}</context_for_action>')

def done(text='Organization complete.'):
    return response(content=text)

def make(*replies):
    return Agent(llm=Script(*replies))

def tools(req):
    return [x['function']['name'] for x in req['tools']]

def test_tag_and_save_in_same_response_are_independent():
    a=make(read(), add('exact saved value',content='<context_for_action>Old fact.</context_for_action>\nNow organize.'),done())
    result=run(a)
    assert result.context_for_action=='Old fact.' and result.termination=='no_tool'
    assert result.loop_mode=='remind_first'
    assert [op.action for op in result.operations]==['read','add']
    assert all(op.success for op in result.operations)
    assert all(tools(req)==['memory_add','memory_read'] for req in a.llm.calls)
    assert [req['prompt'] for req in a.llm.calls[1:]]==['Continue.']*2
    assert receipts(a.llm.calls[-1])[-1]['success']
    assert 'stage' not in result.loop_rounds[0]
    assert not a._phase2_history

@pytest.mark.parametrize('body',[None,'A fact.'])
def test_final_summary_with_tag_finishes_without_retry(body):
    a=make(add(content='<no_intervention/>'),decision(body))
    result=run(a)
    assert len(a.llm.calls)==2 and result.context_for_action==body
    assert result.should_inject==(body is not None)

def test_writing_before_read_or_decision_is_not_blocked():
    a=make(add(),read(),done())
    result=run(a)
    assert all(op.success for op in result.operations)
    assert len(a.memory.knowledge)==1 and 'new' in result.operations[1].content
    assert not result.should_inject

def test_same_response_read_write_and_tag_all_handled():
    a=make(response(call('memory_read',{'bank_id':'knowledge'},'r'),
        call('memory_add',{'content':'new fact'},'a'),content='<no_intervention/>'),done())
    result=run(a)
    assert [op.success for op in result.operations]==[True,True]
    assert '(empty)' in result.operations[0].content
    assert result.loop_rounds[0]['decision_accepted']
    assert len(a.llm.calls)==2

def test_latest_decision_replaces_earlier_decision_without_stage_lock():
    a=make(add(content='<context_for_action>initial</context_for_action>'),decision('revised'))
    assert run(a).context_for_action=='revised'

def test_failure_receipt_does_not_cancel_independent_reminder():
    a=make(response(call('memory_add',{'content':''},'bad'),content='<context_for_action>old fact</context_for_action>'),done())
    result=run(a)
    assert not result.operations[0].success and result.context_for_action=='old fact'
    assert not a.memory.knowledge and not receipts(a.llm.calls[1])[0]['success']

def test_failed_tool_can_be_corrected_without_replaying_successful_write():
    a=make(response(call('memory_add',{'content':'kept'},'a'),call('memory_add',{'content':''},'bad')),
           add('corrected','fix'),done())
    result=run(a)
    assert [op.success for op in result.operations]==[True,False,True]
    assert len(a.memory.knowledge)==2

def test_no_tool_reply_finishes_without_forcing_tag_or_save():
    a=make(done('Nothing to save.'))
    result=run(a)
    assert len(a.llm.calls)==1 and not result.should_inject
    assert not result.operations

@pytest.mark.parametrize('text',['','...','<no_intervention/>','Done. <no_intervention/>',
    '```python\nx=1\n```','没有需要保存的信息。'])
def test_no_tool_completion_does_not_require_special_format(text):
    assert is_organize_completion(done(text))

@pytest.mark.parametrize('field',['finish_reason','stop_reason'])
def test_explicit_transport_truncation_still_fails(field):
    a=make(response(content='Done.',**{field:'max_tokens'}))
    assert not is_organize_completion(response(content='Done.',**{field:'max_tokens'}))
    with pytest.raises(GAHistoryIntegrityError):run(a)

def test_successful_chains_and_error_receipts_have_no_new_retry_gate():
    a=make(*[response(call('code_run',{},f'e{i}')) for i in range(4)],
           *[add(str(i),f'a{i}') for i in range(7)],done())
    result=run(a)
    assert len(result.operations)==11 and len(a.memory.knowledge)==7
    assert all(not op.success for op in result.operations[:4])

def test_continuous_native_history_and_new_wake_decision_reset():
    a=make(add('saved','a',content='<context_for_action>first</context_for_action>'),done(),read(),done())
    run(a)
    result=run(a,'EXACT NEW BATCH',4)
    assert not result.should_inject
    assert a.llm.calls[2]['prompt']=='<task_trajectory>\nEXACT NEW BATCH\n</task_trajectory>'
    assert str(a.llm.calls[2]['message_history']).count('Original exact task')==1
    assert len([m for m in provider_history(a._phase1_history) if m['role']=='tool'])==2

def test_archived_reminder_bodies_still_preserve_code():
    cases=json.loads((Path(__file__).parent/'fixtures/reminder_code_regressions.json').read_text())
    for case in cases:
        a=make(add(content=case['raw_public_reply']),done())
        assert run(a).context_for_action==case['expected_reminder']

def test_provider_failure_and_cancellation_propagate():
    for error in [RuntimeError('failure'),asyncio.CancelledError()]:
        a=make(add(content='<context_for_action>not yet delivered</context_for_action>'),error)
        with pytest.raises((GAHistoryIntegrityError,asyncio.CancelledError)):run(a)
        assert len(a.memory.knowledge)==1

@pytest.mark.parametrize('provider',['anthropic','openai'])
def test_native_provider_continuity(provider,monkeypatch,tmp_path):
    from test_predictive_visible_basis import provider_llm,install,rows
    llm,wire=provider_llm(provider,[
        {'text':'Read.', 'calls':[('r','memory_read',{'bank_id':'knowledge'})]},
        {'text':'<context_for_action>Old evidence.\n```python\nx=1\n```</context_for_action>',
         'calls':[('a','memory_add',{'content':'new fact'})]},
        {'text':'Finished. <context_for_action>Old evidence.\n```python\nx=1\n```</context_for_action>'}],monkeypatch)
    a=Agent(llm=llm);install(a,tmp_path);result=run(a)
    assert len(wire)==3 and len(a.memory.knowledge)==1
    assert result.context_for_action=='Old evidence.\n```python\nx=1\n```'
    assert ('signed-private-fixture' if provider=='anthropic' else 'opaque-private-fixture') in str(wire[-1])
    assert rows(tmp_path,'memory_cycle.jsonl')[0]['outcome']=='no_tool'

def test_host_delivers_once_after_loop_finishes(tmp_path):
    from episode import construct_upstream
    host=construct_upstream(tmp_path/'agent',research_candidate='pma_predictive_read_context_v1',memory_api_key='synthetic',memory_api_base='https://example.invalid')
    pending=[];replies=iter([add(content='<context_for_action>Old fact.\n```python\nx=1\n```</context_for_action>'),done()])
    async def llm_call(**kwargs):
        pending.append(host._pending_injection);return next(replies)
    host._memory_llm.call=llm_call
    host._memory_agent.set_phase1_context(task='original',trajectory='');host._task_description='original'
    asyncio.run(host._trigger_memory_agent(1))
    assert pending==[None,None]
    assert 'Old fact.\n```python\nx=1\n```' in host._get_memory_system_prompt()
    assert host._get_memory_system_prompt() is None

@pytest.mark.parametrize('case',json.loads((Path(__file__).parent/'fixtures/prompt_guided_early_add_regressions.json').read_text()),ids=lambda c:f"{c['task']}-{c['cycle_step']}")
def test_archived_replies_expose_existing_parameter_error_not_stage_rejection(case):
    a=make(response(*case['tool_calls'],content=case['content']),done())
    result=run(a)
    assert len(a.llm.calls)==2
    # The historical replies also supplied bank_id to memory_add. Removing a
    # lifecycle gate does not silently rewrite their invalid native arguments.
    assert all(not op.success and op.error=='memory_add accepts only content'
               for op in result.operations)
    assert not a.memory.knowledge
    assert result.loop_rounds[0]['decision_accepted']
    assert len(receipts(a.llm.calls[1]))==len(case['tool_calls'])

    corrected=[call('memory_add', {'content':json.loads(c['function']['arguments'])['content']}, c['id'])
               for c in case['tool_calls']]
    b=make(response(*corrected,content=case['content']),done())
    repaired=run(b)
    assert all(op.success for op in repaired.operations)
    assert [entry['content'] for entry in b.memory.to_dict()['knowledge']]==[
        json.loads(c['function']['arguments'])['content'] for c in case['tool_calls']]
