"""Offline GA-history parity and PMA continuity tests; no providers called."""
import ast, asyncio, copy, json, sys, types, unittest, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
V=P/'vendor/pma_89e5c0d/src/memory_agent'
su=types.ModuleType('shortuuid');su.uuid=lambda:uuid.uuid4().hex;sys.modules['shortuuid']=su
for name,path in [('memory_agent',V),('memory_agent.memory',V/'memory')]:
 m=types.ModuleType(name);m.__path__=[str(path)];sys.modules[name]=m
from memory_agent.memory.memory_agent import MemoryAgent
from memory_agent.memory.universal_memory import UniversalMemory
from memory_agent.memory import ga_context_history as g

class LLM:
 def __init__(self):self.calls=[]
 async def call(self,**kw):
  self.calls.append(copy.deepcopy(kw))
  if kw.get('tools'):
   k=sum(bool(c.get('tools')) for c in self.calls)
   return types.SimpleNamespace(content='note-'+str(k),tool_calls=[
    types.SimpleNamespace(id='call-'+str(k),function=types.SimpleNamespace(name='memory_add',arguments=json.dumps({'content':'memory-'+str(k)})))],
    reasoning_content='private', thinking_blocks=[{'type':'thinking','thinking':'private','signature':'opaque'}])
  return types.SimpleNamespace(content='<no_intervention/>',reasoning_content='never add this private reasoning')

class Tests(unittest.IsolatedAsyncioTestCase):
 def test_exact_ga_functions_reused(self):
  original=ast.parse((ROOT/'GenericAgent-main/llmcore.py').read_text(encoding='utf-8'))
  copied=ast.parse((V/'memory/ga_context_history.py').read_text(encoding='utf-8'))
  for name in ('compress_history_tags','_sanitize_leading_user_msg','trim_messages_history','_msgs_claude2oai'):
   a=next(x for x in original.body if isinstance(x,ast.FunctionDef) and x.name==name)
   b=next(x for x in copied.body if isinstance(x,ast.FunctionDef) and x.name==name)
   self.assertEqual(ast.dump(a,include_attributes=False),ast.dump(b,include_attributes=False),name)
 async def test_separate_histories_receipts_and_no_old_window_resend(self):
  llm=LLM();a=MemoryAgent(llm=llm,memory=UniversalMemory())
  await a.process('TASK + steps 1-8',8);await a.process('TASK + steps 9-16',16)
  self.assertEqual(len(llm.calls),4)
  self.assertEqual(llm.calls[0]['message_history'],[]);self.assertEqual(llm.calls[1]['message_history'],[])
  p1=llm.calls[2];p2=llm.calls[3]
  self.assertIn('steps 1-8',json.dumps(p1['message_history']));self.assertIn('steps 9-16',p1['prompt'])
  self.assertNotIn('steps 1-8',p1['prompt']);self.assertNotIn('steps 9-16',json.dumps(p1['message_history']))
  self.assertIn('call-1',json.dumps(p1['message_history']));self.assertIn('memory-1',json.dumps(p1['message_history']))
  self.assertNotIn('call-1',json.dumps(p2['message_history']));self.assertIn('steps 1-8',json.dumps(p2['message_history']))
  self.assertNotIn('never add this private reasoning',json.dumps(llm.calls))
  self.assertEqual(p1['message_history'][1]['thinking_blocks'][0]['signature'],'opaque')
  self.assertEqual([e.content for e in a.memory.knowledge],['memory-1','memory-2'])
  a.reset_conversation_history();self.assertEqual(a._phase1_history,[]);self.assertEqual(a._phase2_history,[])
  self.assertEqual(len(a.memory.knowledge),2)
 def test_trim_preserves_current_and_handles_orphan_results(self):
  g.compress_history_tags._cd=0
  history=[]
  for i in range(9):
   history.extend([{'role':'user','content':[{'type':'text','text':str(i)+'x'*12000}]},
                   {'role':'assistant','content':[{'type':'tool_use','id':f'c{i}','name':'memory_add','input':{'content':'y'*2000}}]},
                   {'role':'user','content':[{'type':'tool_result','tool_use_id':f'c{i}','content':'ok'}]}])
  prior=g.prepare_history(history,'CURRENT_MARKER')
  self.assertEqual(history[-1]['content'][-1]['text'],'CURRENT_MARKER')
  self.assertLess(len(history),28)
  self.assertNotIn('CURRENT_MARKER',json.dumps(prior))
  self.assertNotEqual(prior[0]['role'],'tool')
 async def test_malformed_tool_batch_is_atomic(self):
  class Bad:
   async def call(self,**kw):
    return types.SimpleNamespace(content='',reasoning_content=None,thinking_blocks=None,tool_calls=[
     types.SimpleNamespace(id='1',function=types.SimpleNamespace(name='memory_add',arguments={'content':'valid'})),
     types.SimpleNamespace(id='2',function=types.SimpleNamespace(name='memory_add',arguments='{'))])
  a=MemoryAgent(llm=Bad(),memory=UniversalMemory())
  with self.assertRaises(g.GAHistoryIntegrityError):await a.process('task',1)
  self.assertEqual(len(a.memory.knowledge),0)
 async def test_missing_signed_thinking_fails_closed_before_write(self):
  class Bad:
   async def call(self,**kw):
    return types.SimpleNamespace(content='',reasoning_content='private',thinking_blocks=None,tool_calls=[
     types.SimpleNamespace(id='1',function=types.SimpleNamespace(name='memory_add',arguments={'content':'must not save'}))])
  a=MemoryAgent(llm=Bad(),memory=UniversalMemory())
  with self.assertRaises(g.GAHistoryIntegrityError):await a.process('task',1)
  self.assertEqual(len(a.memory.knowledge),0)
 async def test_p2_history_integrity_error_is_not_swallowed(self):
  a=MemoryAgent(llm=LLM(),memory=UniversalMemory())
  async def fail(prompt):raise g.GAHistoryIntegrityError('bad history')
  a._call_llm_phase2=fail
  with self.assertRaises(g.GAHistoryIntegrityError):await a.process('task',1)
 def test_signed_blocks_roundtrip_without_compression(self):
  signed=[{'type':'thinking','thinking':'x'*3000,'signature':'opaque-signature'}, {'type':'redacted_thinking','data':'opaque-data'}]
  history=[{'role':'user','content':[{'type':'text','text':'task'}]},
           {'role':'assistant','content':[{'type':'text','text':'done'}], '_provider_thinking_blocks':copy.deepcopy(signed)}]
  for i in range(6):history.extend([{'role':'user','content':[{'type':'text','text':str(i)}]},{'role':'assistant','content':[{'type':'text','text':'ok'}]}])
  g.compress_history_tags._cd=4
  prior=g.prepare_history(history,'now')
  self.assertEqual(history[1]['_provider_thinking_blocks'],signed)
  self.assertEqual(next(x for x in prior if x.get('thinking_blocks'))['thinking_blocks'],signed)
 async def test_audit_redacts_provider_thinking_but_forwards_original(self):
  import time
  tree=ast.parse((P/'worker_main.py').read_text(encoding='utf-8'))
  fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='install_transport_audit')
  recorded=[];forwarded=[]
  async def call(**kw):forwarded.append(kw);return 'ok'
  ns={'Path':Path,'copy':copy,'time':time,'append_private_audit':lambda path, obj:recorded.append(copy.deepcopy(obj))}
  exec(compile(ast.Module(body=[fn],type_ignores=[]),str(P/'worker_main.py'),'exec'),ns)
  agent=types.SimpleNamespace(_memory_llm=types.SimpleNamespace(call=call))
  ns['install_transport_audit'](agent,Path('/tmp'))
  h=[{'role':'assistant','content':'public','thinking_blocks':[{'type':'thinking','thinking':'SECRET_THOUGHT','signature':'SECRET_SIG'}, {'type':'redacted_thinking','data':'SECRET_DATA'}]}]
  await agent._memory_llm.call(prompt='p',system='s',message_history=h)
  self.assertEqual(forwarded[0]['message_history'],h)
  for secret in ('SECRET_THOUGHT','SECRET_SIG','SECRET_DATA'):
   self.assertNotIn(secret,json.dumps(recorded))
  self.assertEqual(h[0]['thinking_blocks'][0]['signature'],'SECRET_SIG')
 async def test_dictionary_tool_calls_preserve_id_and_receipt(self):
  class L:
   def __init__(self):self.calls=[]
   async def call(self,**kw):
    self.calls.append(copy.deepcopy(kw))
    if kw.get('tools'):
     return types.SimpleNamespace(content='',reasoning_content=None,thinking_blocks=None,tool_calls=[{'id':'dict-call','type':'function','function':{'name':'memory_add','arguments':'{"content":"saved"}'}}])
    return types.SimpleNamespace(content='<no_intervention/>',reasoning_content=None,thinking_blocks=None)
  llm=L();a=MemoryAgent(llm=llm,memory=UniversalMemory())
  await a.process('first',1);await a.process('second',8)
  old=llm.calls[2]['message_history']
  self.assertIn('dict-call',json.dumps(old));self.assertEqual([x.content for x in a.memory.knowledge],['saved','saved'])
 async def test_profile_wrapper_forwards_history_and_profile(self):
  tree=ast.parse((P/'episode.py').read_text(encoding='utf-8'))
  fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='construct_upstream')
  captured=[]
  class Base:pass
  class MemoryLLM:
   async def call(self,**kw):captured.append(kw);return 'ok'
  class Agent:
   def __init__(self,**kw):self._llm=kw['llm'];self._memory_llm=MemoryLLM()
  ns={'Path':Path,'Any':object,'DisabledActorLLM':Base,'MemoryEnabledTerminus2':Agent}
  module=ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),fn],type_ignores=[]))
  exec(compile(module,str(P/'episode.py'),'exec'),ns)
  profile={'provider':'anthropic','api_mode':'messages','model':'claude-opus-4-8','thinking_type':'adaptive','apibase':'fixture','apikey':'fixture','temperature':1,'reasoning_effort':'high','max_tokens':8192,'read_timeout':300}
  agent=ns['construct_upstream'](Path('/tmp'),memory_profile=profile)
  history=[{'role':'user','content':'old'},{'role':'assistant','content':'reply'}]
  await agent._memory_llm.call(prompt='new',system='s',tools=None,message_history=history)
  self.assertEqual(captured[0]['message_history'],history);self.assertEqual(captured[0]['thinking'],{'type':'adaptive'})
  self.assertEqual(captured[0]['max_tokens'],8192)
if __name__=='__main__':unittest.main()
