"""Independent synthetic contract tests, outside implementation tree."""
import asyncio
import copy
import json
import socket
from types import SimpleNamespace
import pytest
from memory_agent.memory.read_context_predictive_memory_agent import ReadContextPredictiveMemoryAgent
from memory_agent.memory.ga_context_history import GAHistoryIntegrityError, provider_history
from responses_memory_llm import response_input


@pytest.fixture(autouse=True)
def prohibit_real_network(monkeypatch):
    original_connect = socket.socket.connect
    original_socketpair = socket.socketpair
    def blocked(*args, **kwargs):
        raise AssertionError('Independent offline test attempted network access')
    def local_socketpair(*args, **kwargs):
        with monkeypatch.context() as local:
            local.setattr(socket.socket, 'connect', original_connect)
            return original_socketpair(*args, **kwargs)
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)
    monkeypatch.setattr(socket, 'socketpair', local_socketpair)


def tool(name, arguments, ident):
    return {'id':ident, 'function': {'name':name,'arguments':json.dumps(arguments)}}

def reply(content='', calls=(), **kwargs):
    return SimpleNamespace(content=content,tool_calls=list(calls),**kwargs)

class Fake:
    def __init__(self, *replies):
        self.replies=list(replies)
        self.calls=[]
    async def call(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if not self.replies:
            raise AssertionError('Unexpected additional model request')
        value=self.replies.pop(0)
        if isinstance(value, BaseException): raise value
        return value

def wake(agent, batch='', step=1):
    agent.set_phase1_context(task='immutable original task', trajectory=batch)
    return asyncio.run(agent.process('MUST NOT INSERT A SECOND PHASE OBSERVATION', step))

def make(*replies):
    return ReadContextPredictiveMemoryAgent(llm=Fake(*replies))


def test_terminal_tool_results_survive_next_wake_in_native_order():
    a=make(reply('<no_intervention/>', [tool('memory_add', {'content':'once'},'a')]),
           reply('<no_intervention/>'))
    first=wake(a)
    assert len(a.llm.calls)==1 and len(first.operations)==1
    assert not first.should_inject and len(a.memory.knowledge)==1
    wake(a,'NEXT EXACT BATCH',8)
    assert len(a.llm.calls)==2 and len(a.memory.knowledge)==1
    req=a.llm.calls[-1]
    assert req['prompt']=='NEXT EXACT BATCH'
    actual=response_input(req['message_history'], req['prompt'])
    kinds=[x.get('type',x.get('role')) for x in actual]
    assert kinds==['user','assistant','function_call','function_call_output','user']
    assert actual[-2]['call_id']=='a' and json.loads(actual[-2]['output'])['success'] is True
    assert str(req).count('immutable original task')==1
    assert 'MUST NOT INSERT' not in str(req)
    assert not a._phase2_history


def test_read_add_read_snapshots_before_terminal_is_accepted():
    a=make(reply('<context_for_action>Use the recorded endpoint.</context_for_action>', [
        tool('memory_read', {'bank_id':'knowledge'},'r1'),
        tool('memory_add', {'content':'endpoint=443'},'a'),
        tool('memory_read', {'bank_id':'knowledge'},'r2')]))
    result=wake(a)
    assert len(a.llm.calls)==1 and result.should_inject
    assert len(result.operations)==3
    assert 'endpoint=443' not in result.operations[0].content
    assert 'endpoint=443' in result.operations[2].content
    history=provider_history(a._phase1_history)
    receipts=[json.loads(x['content']) for x in history if x['role']=='tool']
    assert len(receipts)==3 and all(x['success'] for x in receipts)


def test_partial_success_invalidates_same_response_terminal_without_replay():
    a=make(reply('<context_for_action>DO NOT SEND</context_for_action>', [
        tool('memory_add', {'content':'preserve success'},'a'),
        tool('memory_add', {'content':''},'bad')]), reply('<no_intervention/>'))
    result=wake(a)
    assert not result.should_inject and len(a.llm.calls)==2
    assert len(a.memory.knowledge)==1
    assert [x.success for x in result.operations]==[True, False]
    receipts=[json.loads(x['content']) for x in a.llm.calls[1]['message_history'] if x['role']=='tool']
    assert [x['success'] for x in receipts]==[True, False]
    assert len([x for x in a._phase1_history if x['role']=='assistant'])==2


@pytest.mark.parametrize('bad',[
    '', 'text without a decision', '<context_for_action></context_for_action>',
    '<context_for_action>unclosed', '<no_intervention/><no_intervention/>',
    '<no_intervention/><context_for_action>x</context_for_action>',
    '<context_for_action>x</context_for_action><context_for_action>y</context_for_action>',
    '<thinking><context_for_action>private</context_for_action></thinking>',
    '<think><no_intervention/></think>',
])
def test_invalid_public_decision_gets_only_one_repair_then_fails(bad):
    a=make(reply(bad),reply(bad))
    with pytest.raises(GAHistoryIntegrityError): wake(a)
    assert len(a.llm.calls)==2 and len(a.memory.knowledge)==0


def test_reasoning_channel_terminal_cannot_complete():
    a=make(reply('',reasoning_content='<no_intervention/>',thinking_blocks=[
        {'type':'thinking','thinking':'<no_intervention/>','signature':'s'}]),
        reply('<no_intervention/>'))
    result=wake(a)
    assert len(a.llm.calls)==2 and not result.should_inject


def test_successful_tool_chains_are_not_forced_or_capped_to_two_calls():
    replies=[reply(calls=[tool('memory_add', {'content':f'value{i}'},f'a{i}')]) for i in range(7)]
    a=make(*replies,reply('<no_intervention/>'))
    result=wake(a)
    assert len(a.llm.calls)==8 and len(a.memory.knowledge)==7 and len(result.operations)==7


def test_provider_failure_keeps_once_only_prior_mutation():
    a=make(reply(calls=[tool('memory_add',{'content':'saved'},'a')]),RuntimeError('synthetic'))
    with pytest.raises(GAHistoryIntegrityError): wake(a)
    assert len(a.llm.calls)==2 and len(a.memory.knowledge)==1
    receipts=[x for x in provider_history(a._phase1_history) if x['role']=='tool']
    assert len(receipts)==1 and json.loads(receipts[0]['content'])['success'] is True


def test_cancellation_keeps_prior_mutation_and_propagates():
    a=make(reply(calls=[tool('memory_add',{'content':'saved'},'a')]),asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError): wake(a)
    assert len(a.llm.calls)==2 and len(a.memory.knowledge)==1


def test_conflicting_terminal_does_not_suppress_valid_tools():
    a=make(reply('<no_intervention/><context_for_action>conflict</context_for_action>',
                 [tool('memory_add', {'content':'valid'},'a')]),reply('<no_intervention/>'))
    result=wake(a)
    assert len(a.llm.calls)==2 and len(a.memory.knowledge)==1 and not result.should_inject


def test_format_repair_can_reset_after_actual_tool_progress():
    a=make(reply('missing decision'),
        reply(calls=[tool('memory_add',{'content':'progress'},'a')]),
        reply('still working'),reply('<no_intervention/>'))
    result=wake(a)
    assert len(a.llm.calls)==4 and len(a.memory.knowledge)==1 and not result.should_inject


def test_actual_openai_terminal_tools_replay_on_next_wake():
    import httpx
    from openai import AsyncOpenAI
    from responses_memory_llm import ResponsesMemoryLLM
    llm=ResponsesMemoryLLM(dict(model='gpt-6.1-sol', model_context_window=200000,
        max_tokens=8192,reasoning_effort='high',max_retries=0,read_timeout=30,
        apikey='synthetic',apibase='https://example.invalid/v1'))
    wire=[]
    def handler(req):
        wire.append(json.loads(req.content))
        n=len(wire)
        output=[{'type':'reasoning','id':f'r{n}','encrypted_content':f'opaque{n}','summary':[]},
            {'type':'message','id':f'm{n}','role':'assistant','status':'completed','content':[
                {'type':'output_text','text':'<no_intervention/>','annotations':[]}]}]
        if n==1:
            output.append({'type':'function_call','id':'fc','call_id':'add','name':'memory_add',
                'arguments':'{"content":"Saved only once"}','status':'completed'})
        return httpx.Response(200,json={'id':f'resp{n}','object':'response','created_at':1,
            'status':'completed','model':llm.model,'output':output,
            'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}})
    llm.client=AsyncOpenAI(api_key='synthetic',max_retries=0,base_url='https://example.invalid/v1',
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    a=ReadContextPredictiveMemoryAgent(llm=llm)
    wake(a)
    assert len(wire)==1
    wake(a,'second wake',8)
    assert len(wire)==2 and len(a.memory.knowledge)==1
    items=wire[1]['input']
    assert [x.get('type',x.get('role')) for x in items]==[
        'user','reasoning','assistant','function_call','function_call_output','user']
    assert next(x for x in items if x.get('type')=='reasoning')['encrypted_content']=='opaque1'
    calls=[x for x in items if x.get('type')=='function_call']
    outputs=[x for x in items if x.get('type')=='function_call_output']
    assert len(calls)==len(outputs)==1 and calls[0]['call_id']==outputs[0]['call_id']=='add'
    assert json.loads(outputs[0]['output'])['success'] is True
    assert all(req['tools'] and req['store'] is False for req in wire)


def test_actual_anthropic_signed_terminal_tools_replay_on_next_wake(monkeypatch):
    import httpx
    import litellm
    from harbor.llms import lite_llm
    from harbor.llms.lite_llm import LiteLLM
    from litellm.llms.anthropic.chat.transformation import AnthropicConfig
    wire=[]
    signed=[{'type':'thinking','thinking':'private synthetic','signature':'signature'},
            {'type':'redacted_thinking','data':'redacted-opaque'}]
    async def completion(**kwargs):
        config=AnthropicConfig()
        options={'max_tokens':1024,'thinking':{'type':'adaptive'}}
        options['tools'],_=config._map_tools(copy.deepcopy(kwargs['tools']))
        wire.append(config.transform_request(model='claude-opus-4-8',
            messages=copy.deepcopy(kwargs['messages']),optional_params=options,
            litellm_params={},headers={}))
        calls=([{'type':'tool_use','id':'add','name':'memory_add','input':{'content':'Saved once'}}]
               if len(wire)==1 else [])
        content=copy.deepcopy(signed)+[{'type':'text','text':'<no_intervention/>'}]+calls
        raw=httpx.Response(200,json={'id':f'msg{len(wire)}','type':'message','role':'assistant',
            'model':'claude-opus-4-8','content':content,'stop_reason':'tool_use' if calls else 'end_turn',
            'stop_sequence':None,'usage':{'input_tokens':1,'output_tokens':1}})
        return config.transform_response(model='claude-opus-4-8',raw_response=raw,
            model_response=litellm.ModelResponse(),logging_obj=SimpleNamespace(post_call=lambda **kw: None),request_data={},
            messages=kwargs['messages'],optional_params=options,litellm_params={},encoding=None)
    monkeypatch.setattr(lite_llm.litellm,'acompletion',completion)
    a=ReadContextPredictiveMemoryAgent(llm=LiteLLM('anthropic/claude-opus-4-8',api_key='synthetic'))
    wake(a)
    assert len(wire)==1
    wake(a,'second wake',8)
    assert len(wire)==2 and len(a.memory.knowledge)==1
    blocks=[b for m in wire[1]['messages'] for b in m['content']]
    assert all(block in blocks for block in signed)
    assert [b['id'] for b in blocks if b['type']=='tool_use']==['add']
    assert [b['tool_use_id'] for b in blocks if b['type']=='tool_result']==['add']
    for i,m in enumerate(wire[1]['messages']):
        if any(b['type']=='tool_use' for b in m['content']):
            assert wire[1]['messages'][i+1]['role']=='user'
            assert wire[1]['messages'][i+1]['content'][0]['type']=='tool_result'
