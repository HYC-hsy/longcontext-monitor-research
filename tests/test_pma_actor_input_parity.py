"""Offline tests of the GA actor input builder and PMA observer projection."""
import ast, copy, json, unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'GenericAgent-main'/'llmcore.py'
T=ast.parse(P.read_text(encoding='utf-8'))
def node(name, cls=ast.FunctionDef):
 return next(n for n in T.body if isinstance(n,cls) and n.name==name)
ns={'copy':copy,'json':json,'_write_llm_log':lambda *a,**k:None}
exec(compile(ast.fix_missing_locations(ast.Module(body=[node('_native_user_content'),node('NativeToolClient',ast.ClassDef)],type_ignores=[])),str(P),'exec'),ns)

class Backend:
 def __init__(self):self.history=[{'role':'user'}];self.model='fixture';self.received=[]
 def ask(self,msg):
  self.received.append(copy.deepcopy(msg))
  if False:yield None
  return None

class Tests(unittest.TestCase):
 def test_projected_input_equals_actual_native_actor_input(self):
  cases=[
   ([{'type':'text','text':'framework context'}],[{'tool_use_id':'a','content':'output'}],['a']),
   ([{'type':'text','text':'  '},{'type':'text','text':'x'}],[{'tool_use_id':'','content':'no id'},{'tool_use_id':'b','content':'B'}],['a','b']),
   ([],[],[]),
   ([{'type':'text','text':'前文\n[WORKING MEMORY]\n后文'}],[],[]),
  ]
  for content,results,pending in cases:
   with self.subTest(content=content,results=results,pending=pending):
    backend=Backend();client=ns['NativeToolClient'].__new__(ns['NativeToolClient']);client.backend=backend;client._pending_tool_ids=list(pending);client.log_path=False
    projected=ns['_native_user_content'](content,results,pending)
    messages=[{'role':'user','content':copy.deepcopy(content),'tool_results':copy.deepcopy(results)}]
    gen=client.chat(messages)
    try:
     while True:next(gen)
    except StopIteration:pass
    self.assertEqual(backend.received[0]['content'],projected)
 def test_empty_history_discards_stale_pending_ids(self):
  backend=Backend();backend.history=[]
  client=ns['NativeToolClient'].__new__(ns['NativeToolClient']);client.backend=backend;client._pending_tool_ids=['stale'];client.log_path=False
  messages=[{'role':'user','content':'new task'}]
  projected=ns['_native_user_content']([{'type':'text','text':'new task'}],[],[])
  gen=client.chat(messages)
  try:
   while True:next(gen)
  except StopIteration:pass
  self.assertEqual(backend.received[0]['content'],projected)
  self.assertNotIn('stale',str(projected))
 def test_native_private_blocks_excluded_visible_text_preserved(self):
  import re
  n={'copy':copy,'re':re};exec(compile(ast.Module(body=[node('_public_response_blocks')],type_ignores=[]),str(P),'exec'),n)
  blocks=[{'type':'thinking','thinking':'hidden sentinel'}, {'type':'text','text':'a'}, {'type':'tool_use','id':'1','name':'x','input':{'v':1}}, {'type':'text','text':'b'}]
  out=n['_public_response_blocks'](blocks)
  self.assertEqual([x['type'] for x in out],['text','tool_use','text']);self.assertNotIn('hidden sentinel',str(out))
 def test_real_native_ask_captures_visible_synthetic_summary(self):
  import re, threading
  owner=node('NativeClaudeSession',ast.ClassDef)
  ask=next(n for n in owner.body if isinstance(n,ast.FunctionDef) and n.name=='ask')
  class Call:
   def __init__(self,name,args,id=''):self.id=id
  class Response:
   def __init__(self,thinking,content,tool_calls,raw):self.content=content;self.raw=raw
  g={'copy':copy,'re':re,'trim_messages_history':lambda *a:None,
     'MockToolCall':Call,'MockResponse':Response}
  funcs=[node('_public_response_blocks'),node('_ensure_text_block'),ask]
  exec(compile(ast.Module(body=funcs,type_ignores=[]),str(P),'exec'),g)
  class Session:
   def __init__(self):self.lock=threading.Lock();self.history=[]
   def raw_ask(self,messages):
    if False:yield None
    return [{'type':'thinking','thinking':'visible_summary_sentinel\nprivate_extra_sentinel'},
            {'type':'tool_use','name':'probe','id':'1','input':{}}]
  session=Session();gen=g['ask'](session,{'role':'user','content':[{'type':'text','text':'task'}]})
  try:
   while True:next(gen)
  except StopIteration as done:result=done.value
  self.assertIn('visible_summary_sentinel',str(result.public_blocks))
  self.assertNotIn('private_extra_sentinel',str(result.public_blocks))
  self.assertEqual([b['type'] for b in result.public_blocks],['text','tool_use'])
  self.assertTrue(result.private_summary_injected)
if __name__=='__main__':unittest.main()
