"""Ordered reminder/organization lifecycle, synthetic providers only."""
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_predictive_memory_read import Script, call, response, run, receipts
from test_predictive_tool_recovery import block_network  # noqa: F401
from memory_agent.memory.read_context_predictive_memory_agent import (
    RemindFirstMemoryAgent as Agent, REMIND_FIRST_SYSTEM, ORGANIZE_START_PROMPT,
    is_organize_completion)
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


def test_old_bank_decision_frozen_then_write_then_no_tool():
    a = make(read(), decision('Old requirement has three dimensions.'),
             add('New guess: two dimensions.'), done())
    a.memory.save_knowledge('Old requirement has three dimensions.')
    result = run(a)
    assert result.context_for_action == 'Old requirement has three dimensions.'
    assert result.should_inject and result.termination == 'organize_no_tool'
    assert result.loop_mode == 'remind_first'
    assert [x['stage'] for x in result.loop_rounds] == ['remind','remind','organize','organize']
    assert [x.action for x in result.operations] == ['read','add']
    assert 'New guess' not in result.operations[0].content
    assert [tools(req) for req in a.llm.calls] == [['memory_read']]*2 + [['memory_add','memory_read']]*2
    assert all(req['system'] == REMIND_FIRST_SYSTEM for req in a.llm.calls)
    assert a.llm.calls[2]['prompt'] == ORGANIZE_START_PROMPT
    assert receipts(a.llm.calls[3])[-1]['success']
    assert not a._phase2_history


def test_read_and_decision_in_one_reply_cannot_decide_before_receipt():
    a = make(read(content='<context_for_action>premature</context_for_action>'),
             decision('After reading.'), done('Nothing to save.'))
    result = run(a)
    assert len(a.llm.calls) == 3 and result.context_for_action == 'After reading.'
    assert not result.loop_rounds[0]['decision_accepted']
    assert result.loop_rounds[1]['bank_read_before_response']
    assert receipts(a.llm.calls[1])[0]['action'] == 'read'


def test_empty_bank_still_requires_read_and_no_save_is_valid():
    a = make(decision(), read(), decision(), done('No information to save.'))
    result = run(a)
    assert not result.should_inject and len(a.llm.calls) == 4
    assert '(empty)' in result.operations[0].content
    assert not a.memory.knowledge


def test_write_before_reminder_is_rejected_without_mutation_or_transition():
    a = make(response(call('memory_add', {'content': 'must not save'}, 'early'),
                      content='<context_for_action>premature</context_for_action>'),
             read(), decision('safe'), done())
    result = run(a)
    assert not a.memory.knowledge
    assert result.operations[0].success is False
    assert 'unavailable in this stage' in result.operations[0].error
    assert not result.loop_rounds[0]['decision_accepted']
    assert result.context_for_action == 'safe'
    assert receipts(a.llm.calls[1])[0]['success'] is False


def test_mixed_read_add_reply_has_no_write_and_no_premature_decision():
    a = make(response(call('memory_read', {'bank_id':'knowledge'}, 'read1'),
                      call('memory_add', {'content':'forbidden'}, 'add1'),
                      content='<no_intervention/>'), decision(), done())
    result=run(a)
    assert [x.success for x in result.operations] == [True,False]
    assert len(a.llm.calls)==3 and not a.memory.knowledge
    assert not result.loop_rounds[0]['decision_accepted']


def test_organization_cannot_replace_frozen_reminder_with_new_tag():
    a = make(read(), decision('old'),
             response(content='<context_for_action>replacement</context_for_action>'),
             add(), done())
    result=run(a)
    assert result.context_for_action=='old' and len(a.llm.calls)==5
    assert not result.loop_rounds[2]['organize_completed']


def test_tool_call_plus_plain_completion_must_observe_receipt():
    a=make(read(),decision(),add(content='Finished.'),done())
    result=run(a)
    assert len(a.llm.calls)==4
    assert not result.loop_rounds[2]['organize_completed']
    assert result.loop_rounds[3]['organize_completed']


def test_success_and_failure_receipts_not_replayed_and_latch_survives_repair():
    a=make(read(),decision('old'), response(
        call('memory_add',{'content':'kept'},'a'),call('memory_add',{'content':''},'bad'),
        content='Finished.'), done())
    result=run(a)
    assert [x.success for x in result.operations]==[True,True,False]
    assert len(a.memory.knowledge)==1 and result.context_for_action=='old'
    assert len(receipts(a.llm.calls[-1]))==3
    assert 'reminder decision remains recorded' in a.llm.calls[-1]['prompt']
    assert 'decide again' not in a.llm.calls[-1]['prompt']


@pytest.mark.parametrize('value', ['', '...', '<think>done</think>', '<thinking>done',
    '<no_intervention/>','<context_for_action>x</context_for_action>',
    '```python\nprint(1)\n```','~~~\n<no_intervention/>\n~~~',
    'max_tokens !!!]','!!!Error: failed','[!!! 流异常中断',
    'Done.<think>unclosed', 'Done.<think>bad</thinking>',
    '<think>outer<thinking>inner</thinking></think>Done.'])
def test_invalid_no_tool_is_not_organization_completion(value):
    assert not is_organize_completion(done(value))
    a=make(read(),decision(),done(value),done(value))
    with pytest.raises(GAHistoryIntegrityError):run(a)
    assert len(a.llm.calls)==4


@pytest.mark.parametrize('value',['Nothing to save.','Done.','没有需要保存的信息。',
    'I saved the information.\n```python\nx = 1\n```'])
def test_ordinary_no_tool_completion_needs_no_magic_keyword(value):
    assert is_organize_completion(done(value))


@pytest.mark.parametrize('field', ['finish_reason','stop_reason'])
def test_explicit_truncation_not_completion(field):
    assert not is_organize_completion(response(content='Done.',**{field:'max_tokens'}))


def test_provider_failure_during_organization_never_releases_latched_reminder():
    a=make(read(),decision('never delivered'),add('saved once'),RuntimeError('failure'))
    with pytest.raises(GAHistoryIntegrityError):run(a)
    assert len(a.memory.knowledge)==1
    assert a._reminder_decision==('context_for_action','never delivered')
    # There was no returned result for the host to enqueue.
    assert len(a.llm.calls)==4


def test_cancellation_propagates_without_result():
    a=make(read(),decision('not delivered'),asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):run(a)


def test_successful_tool_chains_remain_optional_and_not_artificially_capped():
    a=make(read(),decision(),*[add(str(i),f'a{i}') for i in range(7)],done())
    result=run(a)
    assert len(a.llm.calls)==10 and len(a.memory.knowledge)==7
    assert len(result.operations)==8


def test_every_wake_reads_again_and_keeps_native_history_and_task_anchor():
    a=make(read('r1'),decision('first'),add('saved','a1'),done(),
           read('r2'),decision(),done('No additional information.'))
    run(a)
    result=run(a,'EXACT NEW BATCH',4)
    assert len(a.llm.calls)==7 and not result.should_inject
    assert result.operations[0].action=='read'
    req=a.llm.calls[4]
    assert req['prompt']=='<task_trajectory>\nEXACT NEW BATCH\n</task_trajectory>'
    assert str(req['message_history']).count('Original exact task')==1
    assert len(a.memory.knowledge)==1
    assert len([x for x in provider_history(a._phase1_history) if x['role']=='tool'])==3


def test_hidden_or_code_decision_not_accepted():
    a=make(read(),response(content='<thinking><no_intervention/></thinking>'),decision(),done())
    result=run(a)
    assert not result.loop_rounds[1]['decision_accepted']
    assert len(a.llm.calls)==4


def test_archived_reminder_bodies_survive_new_lifecycle():
    cases=json.loads((Path(__file__).parent/'fixtures/reminder_code_regressions.json').read_text())
    for case in cases:
        a=make(read(),response(content=case['raw_public_reply']),add(),done())
        assert run(a).context_for_action==case['expected_reminder']


def test_failed_read_must_be_repaired_before_decision():
    a=make(response(call('memory_read', {'query':'bad'},'bad')),
           decision('premature'),read(),decision('accepted'),done())
    result=run(a)
    assert result.context_for_action=='accepted'
    assert not result.operations[0].success
    assert len(a.llm.calls)==5


def test_consecutive_bad_tool_calls_exhaust_recovery():
    a=make(*[response(call('memory_add', {'content':'blocked'},f'a{i}')) for i in range(3)])
    with pytest.raises(GAHistoryIntegrityError):run(a)
    assert not a.memory.knowledge


@pytest.mark.parametrize('provider', ['anthropic','openai'])
def test_actual_provider_native_continuity_and_recorded_stage(provider, monkeypatch, tmp_path):
    from test_predictive_visible_basis import provider_llm, install, rows
    llm,wire=provider_llm(provider,[
        {'text':'Read old bank.', 'calls':[('r','memory_read',{'bank_id':'knowledge'})]},
        {'text':'<context_for_action>Old evidence.\n```python\nx = 1\n```</context_for_action>'},
        {'text':'Save future information.', 'calls':[('a','memory_add',{'content':'new fact'})]},
        {'text':'Finished.'}],monkeypatch)
    a=Agent(llm=llm)
    install(a,tmp_path)
    result=run(a)
    assert len(wire)==4 and result.context_for_action=='Old evidence.\n```python\nx = 1\n```'
    assert len(a.memory.knowledge)==1
    history=str(wire[-1])
    assert 'new fact' in history
    assert ('signed-private-fixture' if provider=='anthropic' else 'opaque-private-fixture') in history
    responses=rows(tmp_path,'memory_response.jsonl')
    assert len(responses)==4
    cycles=rows(tmp_path,'memory_cycle.jsonl')
    assert cycles[0]['outcome']=='organize_no_tool'
    assert [x['stage'] for x in cycles[0]['loop_rounds']]==['remind']*2+['organize']*2
    receipts_log=rows(tmp_path,'memory_tool_results.jsonl')
    assert [len(x['tool_results']) for x in receipts_log]==[1,0,1,0]


def test_host_only_receives_frozen_reminder_after_organization_completed(tmp_path):
    from episode import construct_upstream
    host=construct_upstream(tmp_path/'agent',research_candidate='pma_predictive_read_context_v1',
                            memory_api_key='synthetic',memory_api_base='https://example.invalid')
    assert type(host._memory_agent).__name__=='RemindFirstMemoryAgent'
    pending=[]
    replies=iter([read(),decision('Old fact.\n```python\nx=1\n```'),add(),done()])
    async def llm_call(**kwargs):
        pending.append(host._pending_injection)
        return next(replies)
    host._memory_llm.call=llm_call
    host._memory_agent.set_phase1_context(task='original',trajectory='')
    host._task_description='original'
    asyncio.run(host._trigger_memory_agent(1))
    assert pending==[None]*4
    injected=host._get_memory_system_prompt()
    assert 'Old fact.\n```python\nx=1\n```' in injected
    assert host._get_memory_system_prompt() is None
    assert len(host._memory.knowledge)==1


def test_host_failure_after_latch_never_queues_reminder(tmp_path):
    from episode import construct_upstream
    host=construct_upstream(tmp_path/'agent',research_candidate='pma_predictive_read_context_v1',
                            memory_api_key='synthetic',memory_api_base='https://example.invalid')
    script=Script(read(),decision('Do not enqueue.'),add(),RuntimeError('failure'))
    host._memory_llm.call=script.call
    host._memory_agent.set_phase1_context(task='original',trajectory='')
    host._task_description='original'
    with pytest.raises(GAHistoryIntegrityError):asyncio.run(host._trigger_memory_agent(1))
    assert host._get_memory_system_prompt() is None
    assert len(host._memory.knowledge)==1


@pytest.mark.parametrize('provider', ['anthropic','openai'])
def test_native_adapter_truncation_cannot_finish_organization(provider, monkeypatch):
    from test_predictive_visible_basis import provider_llm
    llm,wire=provider_llm(provider,[
        {'text':'Read.', 'calls':[('r','memory_read',{'bank_id':'knowledge'})]},
        {'text':'<context_for_action>Never deliver on truncation.</context_for_action>'},
        {'text':'Done.'}],monkeypatch)
    n=0
    if provider=='anthropic':
        from harbor.llms import lite_llm
        original=lite_llm.litellm.acompletion
        async def truncated(**kwargs):
            nonlocal n
            n+=1
            result=await original(**kwargs)
            if n==3:result['choices'][0]['finish_reason']='length'
            return result
        monkeypatch.setattr(lite_llm.litellm,'acompletion',truncated)
    else:
        original=llm.client.responses.create
        async def truncated(**kwargs):
            nonlocal n
            n+=1
            result=await original(**kwargs)
            if n==3:result=result.model_copy(update={'status':'incomplete'})
            return result
        monkeypatch.setattr(llm.client.responses,'create',truncated)
    a=Agent(llm=llm)
    with pytest.raises(GAHistoryIntegrityError):run(a)
    assert len(wire)==3 and a._wake_stage=='organize'
    assert not any(x['organize_completed'] for x in a._unified_rounds)
