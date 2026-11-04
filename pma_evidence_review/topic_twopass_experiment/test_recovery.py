import ast, asyncio, copy, json, re, unicodedata
from pathlib import Path
from types import SimpleNamespace as NS
root=Path(__file__).resolve().parents[2] / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
src=(root/'p1_requirements.py').read_text(encoding='utf-8'); tree=ast.parse(src)
names={'INIT_DRAFT_SYSTEM','INIT_REFINE_SYSTEM','INIT_TOOL','RequirementError','canonical','catalog'}; nodes=[]
for node in tree.body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in node.targets):nodes.append(node)
 elif isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:nodes.append(node)
env={'re':re,'unicodedata':unicodedata,'deepcopy':copy.deepcopy,'encode':lambda x:json.dumps(x,sort_keys=True,separators=(',',':'))}
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'p1_requirements.py','exec'),env)
tree=ast.parse((root/'p1_requirement_agent.py').read_text(encoding='utf-8'));cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='RequirementP1Agent')
for name in ('_initialization_stage','_initialize'):
 f=copy.deepcopy(next(x for x in cls.body if isinstance(x,ast.AsyncFunctionDef) and x.name==name));exec(compile(ast.fix_missing_locations(ast.Module(body=[f],type_ignores=[])),'p1_requirement_agent.py','exec'),env)
class State:
 def __init__(self):self.data={'catalog':None,'cycles':{'init_1':{'initialization_attempts':[]}}};self.fail_freeze=False
 def write(self,fn):
  new=copy.deepcopy(self.data);fn(new)
  if self.fail_freeze and new['catalog'] is not None:
   self.fail_freeze=False;raise OSError('mock freeze failure')
  self.data=new
class Agent:
 _initialize=env['_initialize'];_initialization_stage=env['_initialization_stage']
 def __init__(self,task,responses):
  self.task=task;self.requirement_state=State();self.responses=list(responses);self.calls=[];self.windows=[];self.before_request=None;self.source_archive=NS(capture=lambda *a:self.windows.append(a))
 def _journal(self,x):pass
 def _strip_thinking(self,s):return s
 def _calls(self,response,_):return [{'name':c.function.name,'arguments':json.loads(c.function.arguments)} for c in response.tool_calls]
 async def _call_model(self,**kwargs):
  self.calls.append(kwargs);res=self.responses.pop(0)
  if isinstance(res,Exception):raise res
  return NS(content='',tool_calls=[NS(function=NS(name=res[0],arguments=json.dumps(res[1])))],usage=None)
def response(x):return ('requirements_initialize',{'requirements':x})
async def main():
 tasks=[{'content':'Synthetic task '+str(i)} for i in range(20)]
 assert len(tasks)==20
 for item in tasks:
  a=Agent(item['content'],[response(['Work']),response(['Work with boundary'])]);await a._initialize('init_1')
  assert len(a.calls)==2 and a.requirement_state.data['catalog']==['Work with boundary']
  assert a.task in a.calls[0]['prompt'] and a.task in a.calls[1]['prompt']
  assert 'Work' in a.calls[1]['prompt'] and a.calls[0]['system']==env['INIT_DRAFT_SYSTEM'] and a.calls[1]['system']==env['INIT_REFINE_SYSTEM']
  assert a._initialization_call_counts=={'attempted':2,'completed':2}
  assert len(a.windows)==2 and len(a.requirement_state.data['cycles']['init_1']['initialization_attempts'])==2
 print('PASS: 20 tasks; 2 calls, full task in both, draft only in second, final only frozen')
 a=Agent('task',[response(['Draft']),response(['Final'])]);a.requirement_state.fail_freeze=True
 try:await a._initialize('init_1')
 except OSError:pass
 else:raise AssertionError('freeze failure not raised')
 await a._initialize('init_1');assert len(a.calls)==2 and a.requirement_state.data['catalog']==['Final'] and a._initialization_call_counts=={'attempted':0,'completed':0}
 print('PASS: validated draft/final reused after freeze failure; no duplicate model call')
 a=Agent('task',[response(['Draft']),RuntimeError('uncertain')])
 try:await a._initialize('init_1')
 except RuntimeError:pass
 else:raise AssertionError('uncertain failure not raised')
 try:await a._initialize('init_1')
 except env['RequirementError'] as e:assert e.reason=='initialization_outcome_uncertain'
 else:raise AssertionError('uncertain repeat not blocked')
 assert len(a.calls)==2
 print('PASS: uncertain final blocks silent retry')
 a=Agent('task',[('execute_command',{'command':'x'})])
 try:await a._initialize('init_1')
 except env['RequirementError'] as e:assert e.reason=='expected_one_initialization_call'
 else:raise AssertionError('invalid tool accepted')
 assert len(a.calls)==1 and a.requirement_state.data['catalog'] is None
 print('PASS: unrelated tool rejected, no final call and no frozen catalog')
 print('No real model or full production runtime executed.')
asyncio.run(main())
