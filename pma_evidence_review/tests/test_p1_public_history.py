import ast,copy,json,unittest,asyncio
from pathlib import Path
from types import SimpleNamespace as NS
from pma_evidence_review.tests import test_p1_requirements as f
from pma_evidence_review.tests.test_bank_display import reply
from p1_linked_agent import render_history
from p2_requirement_reminder import RequirementReminderAgent
from p1_source_links import visible_event
ROOT=Path(__file__).resolve().parents[2]

def load_functions(file,names,env):
 t=ast.parse(Path(file).read_text());nodes=[n for n in t.body if isinstance(n,ast.FunctionDef) and n.name in names]
 exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(file),'exec'),env)
 return env

class Native(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import re
  cls.env=load_functions(ROOT/'GenericAgent-main/llmcore.py',['_public_response_blocks','_native_user_content'],{'copy':copy,'re':re})
 def test_public_order_and_hidden_exclusion(self):
  fn=self.env['_public_response_blocks']; raw=[{'type':'thinking','thinking':'SECRET'}, {'type':'text','text':' A\n'}, {'type':'tool_use','id':'c1','name':'run','input':{'cmd':'x\\ny'}}, {'type':'text','text':'后文  '}]
  result=fn(raw);self.assertEqual([x['type'] for x in result],['text','tool_use','text']);self.assertEqual(result[0]['text'],' A\n');self.assertNotIn('SECRET',str(result));self.assertIsNone(fn([{'type':'text','text':'<thinking>SECRET</thinking>'}]))
  raw[2]['input']['cmd']='changed';self.assertEqual(result[1]['input']['cmd'],'x\\ny')
 def test_native_session_tool_only_does_not_publish_synthetic_summary(self):
  import re,threading
  file=ROOT/'GenericAgent-main/llmcore.py';tree=ast.parse(file.read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeClaudeSession');fn=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='ask'))
  env=dict(self.env,copy=copy,re=re,trim_messages_history=lambda *a:None, _parse_text_tool_calls=lambda c:([],c))
  load_functions(file,['_ensure_text_block'],env)
  env['MockToolCall']=lambda name,args,id='':NS(id=id,function=NS(name=name,arguments=json.dumps(args)))
  env['MockResponse']=lambda thinking,content,tool_calls,raw:NS(thinking=thinking,content=content,tool_calls=tool_calls,raw=raw)
  exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),str(file),'exec'),env)
  def raw_ask(messages):
   if False:yield None
   return [{'type':'thinking','thinking':'SECRET private'},{'type':'tool_use','id':'x','name':'read','input':{}}]
  session=NS(lock=threading.RLock(),history=[],raw_ask=raw_ask,task_complete_response=False)
  gen=env['ask'](session,{'role':'user','content':[]})
  try:
   while True:next(gen)
  except StopIteration as done:response=done.value
  self.assertTrue(response.private_summary_injected);self.assertIn('SECRET',response.content)
  self.assertNotIn('SECRET',str(response.public_blocks));self.assertEqual([b['type'] for b in response.public_blocks],['tool_use'])
 def test_private_history_taint_survives_new_runner_and_unknown_history(self):
  env=load_functions(ROOT/'GenericAgent-main/agent_loop.py',['_pma_history_tainted','_pma_update_history_taint'],{})
  backend=NS(history=[]);handler=NS(history_info=[]);safe=NS(private_summary_injected=False,public_blocks=[]);private=NS(private_summary_injected=True,public_blocks=[])
  self.assertFalse(env['_pma_history_tainted'](backend,handler));self.assertFalse(env['_pma_update_history_taint'](False,safe,backend));self.assertTrue(env['_pma_update_history_taint'](False,private,backend));self.assertTrue(env['_pma_history_tainted'](backend,handler));self.assertTrue(env['_pma_update_history_taint'](True,safe,backend))
  self.assertTrue(env['_pma_history_tainted'](NS(history=['existing']),handler));self.assertTrue(env['_pma_history_tainted'](NS(history=[]),NS(history_info=['existing'])))
 def test_user_result_sequence(self):
  fn=self.env['_native_user_content']; blocks=fn([{'type':'text','text':' next\n'}],[{'tool_use_id':'x','content':'中文\\n'}],['x','missing'])
  self.assertEqual([b['type'] for b in blocks],['tool_result','tool_result','text']);self.assertEqual(blocks[1]['content'],'');self.assertEqual(blocks[2]['text'],' next\n')
 def test_render_public_and_legacy(self):
  x=render_history([{'source_alias':'E1','public_blocks':[{'type':'text','text':' before '},{'type':'tool_use','id':'x','name':'read','input':{'f':'a'}},{'type':'text','text':' after '}],'public_results':[{'type':'tool_result','tool_use_id':'x','content':'line 1\nline 2'}]}]);self.assertLess(x.index(' before '),x.index('[tool call'));self.assertLess(x.index('[tool call'),x.index(' after '));self.assertLess(x.index(' after '),x.index('line 1\nline 2'));self.assertNotIn('public_blocks',x)
  old=render_history([{'source_alias':'E2','analysis':'old','commands':['cmd'],'observation':'obs'}]);self.assertIn('original public block order unavailable',old);self.assertIn('old',old)

class Integration(unittest.TestCase):
 setUp=f.RequirementTests.setUp;init=f.RequirementTests.init;save=f.RequirementTests.save;reopen=f.RequirementTests.reopen
 def test_three_window_and_mapping(self):
  entries=[{'event_id':'e'+str(i),'analysis':'reply'+str(i),'observation':'out'+str(i),'public_blocks':[{'type':'text','text':'response '+str(i)}],'public_results':[{'type':'tool_result','tool_use_id':'x','content':'result '+str(i)}]} for i in range(8)]
  self.responses=[self.init(),reply([self.save('latest',source_ids=('E1',))])]
  r=asyncio.run(self.agent.maintain(entries,observation='unchanged retrieval query',cycle_id='a'));self.assertEqual(r['status'],'completed');prompt=self.requests[-1]['prompt']
  self.assertNotIn('response 4',prompt);self.assertIn('response 5',prompt);self.assertIn('response 7',prompt);self.assertIn('[E1]',prompt);self.assertNotIn('public_blocks',prompt)
  self.assertEqual(len(self.agent.links.state['events']),8);ref=next(iter(self.agent.links.state['refs'].values()));sid=ref['sources'][0]['source_id'];self.assertEqual(self.agent.links.state['events'][sid]['raw']['event_id'],'e5')
  self.assertEqual([r['event_id'] for r in self.agent._raw_generation_context['events']],['e5','e6','e7']);self.assertEqual([r['event_id'] for r in RequirementReminderAgent._visible_steps(None,entries)],['e5','e6','e7'])
 def test_rejected_public_projection_never_exposes_private_text(self):
  bad={'event_id':'bad','analysis':'<thinking>SECRET</thinking> visible','observation':'tool result', 'public_blocks':[{'type':'text','text':'<thinking>SECRET</thinking> visible'}], 'public_results':[]}
  self.responses=[self.init(),reply([self.save('memory',source_ids=('E1',))])]
  self.assertEqual(asyncio.run(self.agent.maintain([bad],observation='query',cycle_id='safe'))['status'],'completed')
  self.assertNotIn('SECRET',self.requests[-1]['prompt'])
  self.assertNotIn('SECRET',json.dumps(self.agent.links.state))
  row=RequirementReminderAgent._visible_steps(None,[bad])[0]; self.assertNotIn('SECRET',json.dumps(row))
 def test_private_synthetic_summary_not_readable_from_source(self):
  event={'event_id':'a','analysis':'<summary>SECRET</summary>','observation':'ok','public_blocks':[{'type':'tool_use','id':'x','name':'read','input':{}}],'public_results':[{'type':'tool_result','tool_use_id':'x','content':'safe'}]}
  self.responses=[self.init(),reply([self.save('m',source_ids=('E1',))])]
  self.assertEqual(asyncio.run(self.agent.maintain([event],observation='query',cycle_id='private'))['status'],'completed')
  self.assertNotIn('SECRET',self.requests[-1]['prompt']); ref=next(iter(self.agent.links.state['refs'].values())); fields=self.agent.links._fields(ref['sources']); self.assertNotIn('SECRET',str(fields)); self.assertNotIn('SECRET',json.dumps(self.agent.links.state))
  self.assertNotIn('SECRET',json.dumps(RequirementReminderAgent._visible_steps(None,[event])))
 def test_old_untrusted_summary_is_withheld(self):
  old={'source_alias':'E1','analysis':'<summary>SECRET</summary> public','observation':'ok'}
  self.assertNotIn('SECRET',render_history([old])); self.assertIn('withheld',render_history([old]))
 def test_old_context_withheld_but_new_context_readable(self):
  from p1_source_archive import encode, digest
  event={'event_id':'a','observation':'receipt','public_blocks':[{'type':'text','text':'safe'}],'public_results':[]}
  self.responses=[self.init(),reply([self.save('m',source_ids=())])]
  self.assertEqual(asyncio.run(self.agent.maintain([event],observation='query',cycle_id='ctx'))['status'],'completed')
  row=self.agent.memory.knowledge[0];ref=self.agent.links.state['refs'][row.id];target={'kind':'memory','id':row.id,'ref':ref};active=self.agent._active_records()
  good=self.agent.links.read(target,active,view='context',archive=self.agent.source_archive);self.assertNotEqual(good['status'],'legacy_context_unavailable')
  path=self.agent.source_archive.window_path(ref['context_window']);window=json.loads(path.read_text(encoding='utf-8'));window['model_input']='<summary>SECRET</summary>';window.pop('input_projection',None);payload=encode(window);path.write_text(payload,encoding='utf-8');ref['context_sha256']=digest(payload)
  for view in ('context',None):
   result=self.agent.links.read(target,active,view=view,archive=self.agent.source_archive);self.assertEqual(result['status'],'legacy_context_unavailable');self.assertNotIn('SECRET',str(result))
 def test_sliding_references_survive(self):
  entries=[{'event_id':'e'+str(i),'analysis':'r'+str(i),'observation':'o'+str(i)} for i in range(5)]
  self.responses=[self.init(),reply([self.save('first',source_ids=('E1',))])]
  self.assertEqual(asyncio.run(self.agent.maintain(entries,observation='query',cycle_id='first'))['status'],'completed')
  first=next(iter(self.agent.links.state['refs'].values()))['sources'][0]['source_id'];self.assertEqual(self.agent.links.state['events'][first]['raw']['event_id'],'e2')
  self.responses=[reply()]; entries += [{'event_id':'e5','analysis':'r5','observation':'o5'},{'event_id':'e6','analysis':'r6','observation':'o6'}]
  self.assertEqual(asyncio.run(self.agent.maintain(entries,observation='query',cycle_id='next'))['status'],'completed')
  self.assertEqual(self.agent.links.state['events'][first]['raw']['event_id'],'e2'); self.assertNotIn('r2',self.requests[-1]['prompt'].split('## Historical visible events',1)[1].split('## Fixed task topics',1)[0]);self.assertEqual([r['event_id'] for r in self.agent._raw_generation_context['events']],['e4','e5','e6'])
if __name__=='__main__':unittest.main()
