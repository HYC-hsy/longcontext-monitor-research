import ast, asyncio, importlib.util, json, sys, tempfile, types, unittest, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
V=BASE/'vendor/pma_89e5c0d/src/memory_agent'
# Test-only stub for missing shortuuid, not a full environment validation.
su=types.ModuleType('shortuuid'); su.uuid=lambda: uuid.uuid4().hex; sys.modules['shortuuid']=su
for name,path in [('memory_agent',V),('memory_agent.memory',V/'memory')]:
 p=types.ModuleType(name); p.__path__=[str(path)]; sys.modules[name]=p
from memory_agent.memory.memory_agent import MemoryAgent, BANK_TOOLS
from memory_agent.memory.universal_memory import UniversalMemory

def ast_class(file, name, namespace):
 tree=ast.parse(file.read_text()); node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name)
 exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),node],type_ignores=[])),str(file),'exec'),namespace); return namespace[name]

class FakeLLM:
 def __init__(self): self.calls=[]
 async def call(self, **kw):
  self.calls.append(kw)
  if len(self.calls)%2:
   return types.SimpleNamespace(content='',tool_calls=[types.SimpleNamespace(function=types.SimpleNamespace(name='memory_add',arguments={'content':'保存 🧪'}))])
  return types.SimpleNamespace(content='<no_intervention/>')

class Tests(unittest.IsolatedAsyncioTestCase):
 def test_tool_is_only_add(self):
  self.assertEqual([x['function']['name'] for x in BANK_TOOLS],['memory_add'])
 async def test_both_phases_and_full_bank(self):
  bank=UniversalMemory()
  for i in range(65): bank.save_knowledge('entry-'+str(i))
  llm=FakeLLM(); a=MemoryAgent(llm=llm,memory=bank,use_structured_tools=True)
  await a.process('trajectory',8)
  self.assertEqual(len(llm.calls),2); self.assertEqual(len(llm.calls[0]['tools']),1)
  self.assertIn('entry-0',llm.calls[0]['prompt']);self.assertIn('entry-64',llm.calls[0]['prompt'])
  self.assertIn('保存 🧪',llm.calls[1]['prompt']);self.assertNotIn('<knowledge>',llm.calls[1]['prompt'])
  self.assertEqual(bank.knowledge[-1].content,'保存 🧪')
  d=bank.to_dict();self.assertEqual(UniversalMemory.from_dict(d).knowledge[-1].content,'保存 🧪')
 def test_legacy_tool_rejected(self):
  bank=UniversalMemory(); a=MemoryAgent(llm=None,memory=bank)
  x=types.SimpleNamespace(tool_calls=[types.SimpleNamespace(function=types.SimpleNamespace(name='memory_delete',arguments={'memory_id':'x'}))])
  result=a._execute_tool_calls(x); self.assertFalse(result[0].success); self.assertEqual(len(bank),0)
 def test_visible_formatter(self):
  ns={'json':json}; cls=ast_class(V/'memory_enabled_agent.py','MemoryEnabledTerminus2',{'Terminus2':object,'Path':Path,'Any':object,'UniversalMemory':object,'json':json})
  v=cls._format_step_entry({'step':7,'public_blocks':[{'type':'text','text':'A'},{'type':'tool_use','id':'1','name':'shell','input':{'cmd':'x'}},{'type':'text','text':'B'}], 'public_results':[{'type':'tool_result','tool_use_id':'1','content':'ok'}]})
  self.assertLess(v.index('A'),v.index('[Tool call]'));self.assertLess(v.index('[Tool call]'),v.index('\nB'));self.assertLess(v.index('\nB'),v.index('[Tool result]'))
 async def test_eight_and_no_overlap(self):
  import hashlib, os
  ns={'Any':object,'Path':Path,'asyncio':asyncio,'json':json,'hashlib':hashlib,'os':os}
  C=ast_class(BASE/'episode.py','PMAEpisode',ns)
  class Agent:
   def __init__(self): self._accumulated_observations=[{'step':0}];self.groups=[]
   async def _trigger_memory_agent(self,step_count): self.groups.append([x['step'] for x in self._accumulated_observations[-8:]])
  with tempfile.TemporaryDirectory() as d:
   a=Agent(); e=C(a,run_id='r',task_id='t',archive=Path(d)/'archive');e.started=True
   for n in range(1,18):
    e.last_attempt=n
    out=await e._actor_step({'actor_attempt':n,'step_status':'normal','public_blocks':[{'type':'text','text':str(n)}],'public_results':[]})
    self.assertEqual(out['triggered'],n in (8,16))
   self.assertEqual(a.groups,[list(range(1,9)),list(range(9,17))]);self.assertEqual(e.batch_steps,1)
 def test_public_blocks_exclude_private_and_preserve_order(self):
  import re, copy
  src=ROOT/'GenericAgent-main/llmcore.py'; tree=ast.parse(src.read_text())
  fun=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_public_response_blocks')
  ns={'re':re,'copy':copy};exec(compile(ast.Module(body=[fun],type_ignores=[]),str(src),'exec'),ns)
  f=ns['_public_response_blocks']
  blocks=[{'type':'text','text':'before'},{'type':'thinking','thinking':'secret'}, {'type':'tool_use','id':'a','name':'shell','input':{'cmd':'echo'}}]
  got=f(blocks);self.assertEqual([b['type'] for b in got],['text','tool_use']);self.assertNotIn('secret',str(got))
  self.assertIsNone(f([{'type':'text','text':'<thinking>secret</thinking>'}]))
 async def test_skips_and_partial_batch(self):
  import hashlib,os
  C=ast_class(BASE/'episode.py','PMAEpisode',{'Any':object,'Path':Path,'asyncio':asyncio,'json':json,'hashlib':hashlib,'os':os})
  class A:
   def __init__(self): self._accumulated_observations=[{'step':0}];self.groups=[]
   async def _trigger_memory_agent(self,step_count): self.groups.append(step_count)
  with tempfile.TemporaryDirectory() as d:
   a=A();e=C(a,run_id='r',task_id='t',archive=Path(d)/'a');e.started=True
   for n in range(1,10):
    e.last_attempt=n;status='provider_cancelled' if n==3 else ('parse_error' if n==4 else 'normal')
    x=await e._actor_step({'actor_attempt':n,'step_status':status,'public_blocks':[],'public_results':[]})
   self.assertEqual(a.groups,[9]);self.assertEqual(e.batch_steps,0)
   self.assertEqual([x['step'] for x in a._accumulated_observations[1:]],[1,2,4,5,6,7,8,9])
 def test_phase2_contract(self):
  from memory_agent.memory.memory_agent import PHASE1_SYSTEM, PHASE2_SYSTEM
  bank=UniversalMemory();bank.save_knowledge('A saved note');a=MemoryAgent(llm=None,memory=bank)
  prompt=a._build_phase2_prompt('trajectory',8)
  self.assertIn('within the next 10 turns',PHASE1_SYSTEM)
  self.assertIn('necessary to remind',prompt);self.assertIn('A saved note',prompt)
  self.assertIn("agent's actions indicate",PHASE2_SYSTEM)
  self.assertNotIn('coding task',PHASE2_SYSTEM)
  self.assertEqual(a._parse_phase2_response('<context_for_action>hello</context_for_action>'),'hello')
  self.assertIsNone(a._parse_phase2_response('<no_intervention/>'))
if __name__=='__main__': unittest.main()
