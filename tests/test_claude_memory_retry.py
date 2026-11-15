"""No network: provider-call retry boundary, counts, and safe metadata."""
import asyncio
from types import SimpleNamespace
import pytest
import httpx
from litellm.exceptions import InternalServerError
import claude_memory_retry as retry
from test_predictive_tool_recovery import block_network  # noqa: F401


@pytest.fixture
def no_sleep(monkeypatch):
    waits=[]
    async def sleep(n):waits.append(n)
    monkeypatch.setattr(retry.asyncio,'sleep',sleep)
    return waits


def execute(*args,**kwargs):return asyncio.run(retry.call_with_retries(*args,**kwargs))


def test_recovery_exact_count_kwargs_and_safe_logs(no_sleep):
    calls=[];logs=[]
    async def call(**kwargs):
        calls.append(kwargs)
        if len(calls)<3:raise ConnectionError('secret endpoint key do not log')
        return 'ok'
    assert execute(call,max_retries=2,observer=logs.append,prompt='original')=='ok'
    assert len(calls)==3 and no_sleep==[1.5,3]
    assert all(x=={'prompt':'original','max_retries':0,'num_retries':0} for x in calls)
    assert [x['outcome'] for x in logs if x['event']=='attempt_finished']==['retry','retry','success']
    assert all(x['underlying_http_attempts']=='unknown' for x in logs)
    assert 'secret' not in str(logs) and all('duration_seconds' in x for x in logs if x['event']=='attempt_finished')


@pytest.mark.parametrize('n',[0,1,3,8])
def test_exhaustion_means_additional_attempts(n,no_sleep):
    calls=[]
    async def call(**kwargs):calls.append(kwargs);raise TimeoutError('timeout')
    with pytest.raises(TimeoutError):execute(call,max_retries=n)
    assert len(calls)==n+1 and len(no_sleep)==n


@pytest.mark.parametrize('error',[ValueError('bad'),RuntimeError('parse'),PermissionError('local bank'),httpx.LocalProtocolError('bad')])
def test_local_and_parameter_failures_not_retried(error,no_sleep):
    calls=[]
    async def call(**kwargs):calls.append(1);raise error
    with pytest.raises(type(error)):execute(call,max_retries=5)
    assert len(calls)==1 and not no_sleep


@pytest.mark.parametrize('name',['AuthenticationError','BadRequestError','ContextLengthExceededError','OutputLengthExceededError'])
def test_known_nonretryable_errors(name,no_sleep):
    error=type(name,(Exception,),{})('not temporary');error.status_code=500
    async def call(**kwargs):raise error
    with pytest.raises(type(error)):execute(call,max_retries=3)
    assert not no_sleep


def test_actual_reported_disconnection_wrapper_without_status(no_sleep):
    error=InternalServerError(message='aiohttp.ServerDisconnectedError: Server disconnected',model='claude-opus-4-8',llm_provider='anthropic')
    error.status_code=None
    assert retry.is_transient(error)
    count=0
    async def call(**kwargs):
        nonlocal count
        count+=1
        if count==1:raise error
        return 'recovered'
    assert execute(call,max_retries=1)=='recovered' and count==2


@pytest.mark.parametrize('code,expected',[(400,False),(401,False),(403,False),(408,True),(429,True),(500,True),(529,True)])
def test_status_classification(code,expected):
    error=Exception();error.status_code=code
    assert retry.is_transient(error)==expected


def test_retry_after_bounds_and_date(monkeypatch):
    error=Exception();error.response=SimpleNamespace(headers={'retry-after':'7'})
    assert retry.retry_delay(error,0)==7
    error.response.headers['retry-after']='1000';assert retry.retry_delay(error,0)==30
    error.response.headers['retry-after']='nan';assert retry.retry_delay(error,2)==6
    monkeypatch.setattr(retry.time,'time',lambda:0)
    error.response.headers['retry-after']='Thu, 01 Jan 1970 00:00:08 GMT'
    assert retry.retry_delay(error,0)==8


def test_cancel_during_request_and_backoff(monkeypatch):
    logs=[]
    async def cancelled(**kwargs):raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):execute(cancelled,max_retries=3,observer=logs.append)
    assert logs[-1]['outcome']=='cancelled' and len(logs)==2
    logs.clear()
    async def disconnect(**kwargs):raise ConnectionError()
    async def sleep(n):raise asyncio.CancelledError()
    monkeypatch.setattr(retry.asyncio,'sleep',sleep)
    with pytest.raises(asyncio.CancelledError):execute(disconnect,max_retries=3,observer=logs.append)
    assert logs[-1]['event']=='retry_wait_cancelled' and len(logs)==3


def test_audit_failure_not_retried(no_sleep):
    def observer(row):raise OSError('archive')
    async def call(**kwargs):raise AssertionError('must not run')
    with pytest.raises(OSError):execute(call,max_retries=3,observer=observer)
    assert not no_sleep


def test_real_profile_binding_bypasses_decorator_and_tools_execute_once(tmp_path,monkeypatch,no_sleep):
    from episode import construct_upstream
    from worker_main import install_transport_audit
    from harbor.llms import lite_llm
    from test_remind_first_loop import run
    import json
    profile={'provider':'anthropic','api_mode':'messages','model':'claude-opus-4-8',
        'apibase':'https://example.invalid','apikey':'synthetic-only',
        'thinking_type':'adaptive','temperature':1,'reasoning_effort':'high',
        'max_tokens':8192,'read_timeout':300,'max_retries':2}
    host=construct_upstream(tmp_path/'agent',research_candidate='pma_predictive_read_context_v1',memory_profile=profile)
    replies=iter([
        {'content':'Read.','tool_calls':[{'id':'r','type':'function','function':{'name':'memory_read','arguments':'{"bank_id":"knowledge"}'}}]},
        {'content':'Judge and save.','tool_calls':[
            {'id':'s','type':'function','function':{'name':'send_reminder','arguments':'{"content":"remind once"}'}},
            {'id':'a','type':'function','function':{'name':'memory_add','arguments':'{"content":"preserve once"}'}}]},
        {'content':'Finished.'}])
    seen=[]
    async def completion(**kwargs):
        seen.append(kwargs)
        if len(seen) in [1,2]:raise ConnectionError('private endpoint')
        return {'choices':[{'message':next(replies),'finish_reason':'stop'}], 'usage':{'prompt_tokens':1,'completion_tokens':1}}
    monkeypatch.setattr(lite_llm.litellm,'acompletion',completion)
    audit=tmp_path/'audit';audit.mkdir();install_transport_audit(host,audit)
    result=run(host._memory_agent)
    assert len(seen)==5 and no_sleep==[1.5,3]
    assert all(x['max_retries']==x['num_retries']==0 for x in seen)
    assert len(host._memory.knowledge)==1 and host._memory.knowledge[0].content=='preserve once'
    rows=[json.loads(x) for x in (audit/'memory_retry_attempts.jsonl').read_text().splitlines()]
    assert [r['attempt'] for r in rows if r['call_sequence']==1 and r['event']=='attempt_started']==[1,2,3]
    assert {r['call_sequence'] for r in rows}=={1,2,3}
    assert all(r['observed_http_status']=='unknown' for r in rows if r['event']=='attempt_finished')
    assert len([o for o in result.operations if o.action=='add'])==1
    assert len([o for o in result.operations if o.action=='send_reminder'])==1
    assert result.context_for_action=='remind once' and result.loop_mode=='reminder_tool'


def test_real_adapter_retry_exhaustion_not_multiplied(tmp_path,monkeypatch,no_sleep):
    from episode import construct_upstream
    from harbor.llms import lite_llm
    p={'provider':'anthropic','model':'claude-opus-4-8','apibase':'https://example.invalid','apikey':'synthetic',
       'temperature':1,'reasoning_effort':'high','max_tokens':8192,'read_timeout':300,'max_retries':1}
    host=construct_upstream(tmp_path/'a',research_candidate='pma_predictive_read_context_v1',memory_profile=p)
    calls=[]
    async def fail(**kwargs):calls.append(kwargs);raise ConnectionError('failed')
    monkeypatch.setattr(lite_llm.litellm,'acompletion',fail)
    with pytest.raises(ConnectionError):asyncio.run(host._memory_llm.call(prompt='x',system='s'))
    assert len(calls)==2 and no_sleep==[1.5]


def test_archive_retry_field_projection_is_complete():
    import ast
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/archive_ordered_real.py').read_text()
    entry=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.Tuple) and n.elts and isinstance(n.elts[0],ast.Constant) and n.elts[0].value=='memory_retry_attempts.jsonl')
    filename,public,fields=ast.literal_eval(entry)
    assert isinstance(fields,tuple) and 'attempt' in fields and 'exception_status_code' in fields
    row={'attempt':2,'outcome':'retry','exception_status_code':500,'observed_http_status':'unknown','exception_message':'secret'}
    projected={key:row.get(key) for key in fields}
    assert projected['attempt']==2 and projected['outcome']=='retry'
    assert 'exception_message' not in projected


def test_legacy_claude_profile_without_retry_count_preserves_three_attempts(tmp_path,monkeypatch,no_sleep):
    from episode import construct_upstream
    from harbor.llms import lite_llm
    p={'provider':'anthropic','model':'claude-opus-4-8','apibase':'https://example.invalid','apikey':'synthetic',
       'temperature':1,'reasoning_effort':'high','max_tokens':8192,'read_timeout':300}
    host=construct_upstream(tmp_path/'a',research_candidate='pma_predictive_f838_v1',memory_profile=p)
    calls=[]
    async def fail(**kwargs):calls.append(kwargs);raise ConnectionError('failed')
    monkeypatch.setattr(lite_llm.litellm,'acompletion',fail)
    with pytest.raises(ConnectionError):asyncio.run(host._memory_llm.call(prompt='x',system='s'))
    assert len(calls)==3


def test_failure_after_reminder_and_save_never_delivers_partial_wake(tmp_path,monkeypatch,no_sleep):
    from episode import construct_upstream
    from harbor.llms import lite_llm
    from memory_agent.memory.ga_context_history import GAHistoryIntegrityError
    p={'provider':'anthropic','model':'claude-opus-4-8','apibase':'https://example.invalid','apikey':'synthetic',
       'temperature':1,'reasoning_effort':'high','max_tokens':8192,'read_timeout':300,'max_retries':1}
    host=construct_upstream(tmp_path/'a',research_candidate='pma_predictive_read_context_v1',memory_profile=p)
    count=0
    async def completion(**kwargs):
        nonlocal count
        count+=1
        if count>1:raise ConnectionError('disconnected on follow-up')
        return {'choices':[{'message':{'content':'Judge and save.','tool_calls':[
            {'id':'s','type':'function','function':{'name':'send_reminder','arguments':'{"content":"not delivered"}'}},
            {'id':'a','type':'function','function':{'name':'memory_add','arguments':'{"content":"saved once"}'}}]},'finish_reason':'stop'}]}
    monkeypatch.setattr(lite_llm.litellm,'acompletion',completion)
    host._memory_agent.set_phase1_context(task='original',trajectory='')
    host._task_description='original'
    with pytest.raises(GAHistoryIntegrityError):asyncio.run(host._trigger_memory_agent(1))
    assert count==3 and len(host._memory.knowledge)==1
    assert host._memory_agent._recorded_reminders==['not delivered']
    assert host._get_memory_system_prompt() is None


def test_mid_wake_retries_do_not_replay_successful_tools_or_mirror(tmp_path,monkeypatch,no_sleep):
    from episode import construct_upstream
    from harbor.llms import lite_llm
    from worker_main import install_transport_audit
    from task_knowledge_file import TaskKnowledgeFile
    import json
    p={'provider':'anthropic','model':'claude-opus-4-8','apibase':'https://example.invalid','apikey':'synthetic',
       'temperature':1,'reasoning_effort':'high','max_tokens':8192,'read_timeout':300,'max_retries':2}
    host=construct_upstream(tmp_path/'a',research_candidate='pma_predictive_read_context_v1',memory_profile=p)
    directory=tmp_path/'responses';directory.mkdir()
    mirror=TaskKnowledgeFile(host._memory,directory,run_id='r',task_id='t')
    audit=tmp_path/'audit';audit.mkdir();install_transport_audit(host,audit)
    count=0
    async def completion(**kwargs):
        nonlocal count
        count+=1
        if count in [2,3]:raise ConnectionError('mid-wake disconnect')
        message={'content':'Finished.'} if count==4 else {'content':'Judge and save.','tool_calls':[
            {'id':'s','type':'function','function':{'name':'send_reminder','arguments':'{"content":"one reminder"}'}},
            {'id':'a','type':'function','function':{'name':'memory_add','arguments':'{"content":"one entry"}'}}]}
        return {'choices':[{'message':message,'finish_reason':'stop'}]}
    monkeypatch.setattr(lite_llm.litellm,'acompletion',completion)
    host._memory_agent.set_phase1_context(task='original',trajectory='')
    host._task_description='original'
    asyncio.run(host._trigger_memory_agent(1))
    assert count==4 and len(host._memory.knowledge)==1
    assert host._memory_agent._recorded_reminders==['one reminder']
    assert len(json.loads(mirror.path.read_text())['knowledge'])==1
    assert 'one reminder' in host._get_memory_system_prompt()
    assert host._get_memory_system_prompt() is None
    rows=[json.loads(x) for x in (audit/'memory_retry_attempts.jsonl').read_text().splitlines()]
    assert [x['attempt'] for x in rows if x['call_sequence']==2 and x['event']=='attempt_started']==[1,2,3]


@pytest.mark.parametrize('mode',['unified','remind_first','reminder_tool'])
def test_public_archive_preserves_actual_loop_mode_and_rounds(mode):
    import ast
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/archive_ordered_real.py').read_text()
    expr=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.IfExp) and isinstance(n.body,ast.Dict) and any(isinstance(k,ast.Constant) and k.value=='loop_mode' for k in n.body.keys))
    row={'loop_mode':mode,'termination':'wake_no_tool','loop_rounds':[{'round':1,'stage':'manage'}]}
    projected=eval(compile(ast.Expression(expr),'<projection>','eval'),{'row':row,'n':1,'projector':SimpleNamespace(json_value=lambda value,path:value)})
    assert projected==row


def test_execution_identity_covers_retry_and_task_mirror():
    import ast
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/single_run_certification.py').read_text()
    tree=ast.parse(source)
    for target,path in [('PREDICTIVE_SOURCE_FILES','claude_memory_retry.py'),('READ_CONTEXT_PREDICTIVE_SOURCE_FILES','task_knowledge_file.py')]:
        node=next(n for n in tree.body if isinstance(n,ast.Assign) and getattr(n.targets[0],'id',None)==target)
        assert any(isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.endswith(path) for n in ast.walk(node))
