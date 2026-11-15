"""Synthetic provider tests: no real model or Task execution."""
import pytest
from memory_agent.memory.reminder_tool_memory_agent import (
    ReminderToolMemoryAgent as Agent, REMINDER_TOOL_SYSTEM, is_wake_completion)
from test_predictive_memory_read import Script, call, response, run, receipts
from test_predictive_tool_recovery import block_network  # noqa: F401
from test_remind_first_loop import read, add, done


def remind(text='Reminder', ident='remind'):
    return response(call('send_reminder', {'content':text}, ident), content='Judgment.')


def test_no_tools_no_reminder_and_no_hard_read_gate():
    a=Agent(llm=Script(done('Nothing to remind or preserve.')))
    result=run(a)
    assert not result.should_inject and result.context_for_action is None
    assert result.termination=='wake_no_tool' and len(a.llm.calls)==1
    assert {t['function']['name'] for t in a.llm.calls[0]['tools']} == {'memory_add','memory_read','send_reminder'}
    assert '<context_for_action>' not in REMINDER_TOOL_SYSTEM
    assert 'Action Principles' in REMINDER_TOOL_SYSTEM


def test_mixed_ordered_batch_exact_content_and_receipts():
    text='  中文\n```python\nx = "\\n"\n```\n '
    a=Agent(llm=Script(response(call('memory_add',{'content':'new'},'a'),
        call('send_reminder',{'content':text},'r'),
        call('memory_read',{'bank_id':'knowledge'},'b'), content='Selected and judged.'),done()))
    result=run(a)
    assert result.context_for_action==text and result.should_inject
    assert [o.action for o in result.operations]==['add','send_reminder','read']
    actual=receipts(a.llm.calls[1])
    assert len(actual)==3 and actual[1]['status']=='recorded' and actual[1]['delivered'] is False
    assert actual[1]['content']==text and 'new' in actual[2]['content']
    assert all(len(req['tools'])==3 for req in a.llm.calls)


def test_multiple_reminders_retained_not_overwritten_by_final_text():
    a=Agent(llm=Script(remind('first','a'),remind('second','b'),done('No more reminders.')))
    result=run(a)
    assert result.context_for_action=='first\n\nsecond'
    assert len(result.loop_rounds)==3


@pytest.mark.parametrize('args',[{}, {'content':''},{'content':42},{'content':'x','extra':1}])
def test_failed_reminder_receipt_then_correction(args):
    a=Agent(llm=Script(response(call('send_reminder',args,'bad')),remind('correct'),done()))
    result=run(a)
    assert not result.operations[0].success
    assert result.context_for_action=='correct'
    assert receipts(a.llm.calls[1])[0]['success'] is False


def test_failed_tool_does_not_drop_other_successful_calls():
    a=Agent(llm=Script(response(call('code_run',{},'bad'),call('send_reminder',{'content':'keep'},'ok')),done()))
    result=run(a)
    assert [o.success for o in result.operations]==[False,True]
    assert result.context_for_action=='keep'
    assert len(receipts(a.llm.calls[1]))==2


@pytest.mark.parametrize('reason',['length','max_tokens','error'])
def test_truncated_no_tool_does_not_end_wake(reason):
    bad=done('Incomplete result');bad.finish_reason=reason
    assert not is_wake_completion(bad)
    a=Agent(llm=Script(remind(),bad,done()))
    assert len(run(a).loop_rounds)==3


def test_empty_and_error_text_not_completion():
    for text in ['', '!!!Error: provider failed', '[!!! 流异常中断', '<thinking>only hidden</thinking>']:
        assert not is_wake_completion(done(text))
    assert not is_wake_completion(remind())


def test_native_history_and_new_wake_reminders_reset():
    a=Agent(llm=Script(read(),remind('old'),add(),done(),read('r2'),done('Nothing new.')))
    first=run(a)
    a.set_phase1_context(task='Original exact task',trajectory='Next observations')
    import asyncio
    second=asyncio.run(a.process('Next observations',4))
    assert first.context_for_action=='old' and not second.should_inject
    assert 'send_reminder' in str(a.llm.calls[4]['message_history'])


def test_missing_read_body_does_not_trigger_save_guidance():
    a=Agent(llm=Script(read(content=''),remind(),done()))
    run(a)
    assert a.llm.calls[1]['system']==REMINDER_TOOL_SYSTEM


def test_missing_add_body_retains_nonblocking_forecast_soft_reminder():
    a=Agent(llm=Script(add(content=''),done()))
    run(a)
    from memory_agent.memory.read_context_predictive_memory_agent import PUBLIC_FORECAST_REMINDER
    assert a.llm.calls[1]['system']==REMINDER_TOOL_SYSTEM+'\n\n'+PUBLIC_FORECAST_REMINDER


def test_source_identity_tracks_new_runtime_module():
    import ast
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/single_run_certification.py').read_text()
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.Assign) and getattr(n.targets[0],'id',None)=='READ_CONTEXT_PREDICTIVE_SOURCE_FILES')
    assert any('reminder_tool_memory_agent.py' in x.value for x in ast.walk(node) if isinstance(x,ast.Constant) and isinstance(x.value,str))


@pytest.mark.parametrize('provider',['anthropic','openai'])
def test_native_provider_continuity_and_audit(provider,monkeypatch,tmp_path):
    from test_predictive_visible_basis import provider_llm, install, rows
    text='Exact 中文\n```python\nx = 1\n```'
    llm,wire=provider_llm(provider,[
        {'text':'Read.', 'calls':[('r','memory_read',{'bank_id':'knowledge'})]},
        {'text':'Judged and selected.', 'calls':[('s','send_reminder',{'content':text}),('a','memory_add',{'content':'new fact'})]},
        {'text':'Finished.'}],monkeypatch)
    a=Agent(llm=llm);install(a,tmp_path);result=run(a)
    assert result.context_for_action==text and len(wire)==3
    assert ('signed-private-fixture' if provider=='anthropic' else 'opaque-private-fixture') in str(wire[-1])
    assert 'send_reminder' in str(wire[-1]) and 'recorded' in str(wire[-1])
    assert [len(x['tool_results']) for x in rows(tmp_path,'memory_tool_results.jsonl')]==[1,2,0]
    assert rows(tmp_path,'memory_cycle.jsonl')[0]['outcome']=='wake_no_tool'


@pytest.mark.parametrize('provider',['anthropic','openai'])
def test_provider_truncation_after_recording_fails_without_result(provider,monkeypatch):
    from test_predictive_visible_basis import provider_llm
    from memory_agent.memory.ga_context_history import GAHistoryIntegrityError
    llm,wire=provider_llm(provider,[{'text':'Judge.', 'calls':[('s','send_reminder',{'content':'Not delivered'})]}, {'text':'Done.'}],monkeypatch)
    n=0
    if provider=='anthropic':
        from harbor.llms import lite_llm
        original=lite_llm.litellm.acompletion
        async def truncated(**kwargs):
            nonlocal n
            n+=1;value=await original(**kwargs)
            if n==2:value['choices'][0]['finish_reason']='length'
            return value
        monkeypatch.setattr(lite_llm.litellm,'acompletion',truncated)
    else:
        original=llm.client.responses.create
        async def truncated(**kwargs):
            nonlocal n
            n+=1;value=await original(**kwargs)
            if n==2:value=value.model_copy(update={'status':'incomplete'})
            return value
        monkeypatch.setattr(llm.client.responses,'create',truncated)
    a=Agent(llm=llm)
    with pytest.raises(GAHistoryIntegrityError):run(a)
    assert a._recorded_reminders==['Not delivered']
    assert not any(x['wake_completed'] for x in a._unified_rounds)
