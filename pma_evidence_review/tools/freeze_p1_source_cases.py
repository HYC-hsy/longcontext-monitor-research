"""Freeze visible-only development inputs; never evaluates or calls a model."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
sys.path.insert(0,str(STAGE))
from selection_context import project_steps

URLS={
 'p1-lean.zip':'https://github.com/HYC-hsy/longcontext-monitor-research/raw/d9837cd221bb7ae2d1c90cdd0033d94dc328d2cc/pma_evidence_review/diagnostic_packages/PMA_P1_LEAN_SQLITE_OCAML_REAL_DIAGNOSTIC_20261101.zip',
 'no-review.zip':'https://github.com/HYC-hsy/longcontext-monitor-research/raw/1d7eb456203ba86b904b206202c7987702f188ee/pma_evidence_review/diagnostic_packages/PMA_NO_REVIEW_SQLITE_REAL_DIAGNOSTIC_20261101.zip'}


def sha(raw):
 return hashlib.sha256(raw).hexdigest()


def dump(path,value):
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def public_rows(archive,member):
 return [json.loads(line)['record'] for line in archive.read(member).splitlines()]


def events_before(host,step):
 rows=[]
 for record in host:
  event=record['event']
  if event['kind']=='actor_step' and event['actor_attempt']<step:
   rows.append({'event_id':event['event_id'],'step':event['actor_attempt']+1,
     'analysis':event.get('response',''),'plan':event.get('plan'),
     'commands':event.get('commands',[]),'observation':event.get('observation','')})
 return rows[-8:]


def initial_bank(prompt):
 categories=dict(re.findall(r'^([^\s]+) \((knowledge|procedural|gap); derived memory\)',prompt,re.M))
 headers=list(re.finditer(r'^\[([^\s]+) (?:memory_derived|task_instruction|agent_report|tool_command|tool_observation) event_order=\d+ field=[^\n]+\]\n',prompt,re.M))
 bank={'status':'','knowledge':[],'procedural':[],'gaps':[]}
 for index,header in enumerate(headers):
  if ' memory_derived event_order=0 ' not in header.group(0):
   continue
  key=header.group(1)
  end=headers[index+1].start() if index+1<len(headers) else len(prompt)
  text=prompt[header.end():end].rstrip('\n')
  if key=='status':
   bank['status']=text
  elif key in categories:
   category=categories[key]
   bank['gaps' if category=='gap' else category].append({
      'id':key,'content':text,'created_at':'public-visible-reconstruction','access_count':0,'last_accessed':None})
 return bank


def public_case(inputs,case_id,zname,prefix,step,dimensions):
 path=inputs/zname
 with zipfile.ZipFile(path) as z:
  members={kind:prefix+name for kind,name in (
    ('host','host-events.jsonl'),('requests','maintenance-selection-requests.jsonl'),
    ('cycles','maintenance-cycles.jsonl'))}
  host=public_rows(z,members['host'])
  requests={x['cycle_step']:x for x in public_rows(z,members['requests']) if x['phase']=='maintenance'}
  cycles=public_rows(z,members['cycles'])
  task=host[0]['event']['initial_user_content']
  bank=initial_bank(requests[step]['prompt'])
  current=events_before(host,step)
  sources,refs={},[]
  for entry in bank['knowledge']+bank['procedural']+bank['gaps']:
   matches=[]
   for cycle in cycles:
    if cycle['step']>=step:
     continue
    for op in cycle['report'].get('operations',[]):
     if (op.get('success') and op.get('memory_id')==entry['id'] and
         op.get('content')==entry['content'] and str(op.get('action','')).startswith('save_')):
      matches.append(cycle['step'])
   if matches:
    origin=max(matches);window_id='origin_'+str(origin)
    projected,_=project_steps(events_before(host,origin))
    for row,raw in zip(projected,events_before(host,origin)):
     row.update(event_id=raw['event_id'],presentation='historical_visible_event')
    sources[window_id]={'window_id':window_id,'model_input':requests[origin]['prompt'],
      'visible_events':projected,'historical_cycle_step':origin}
    refs.append({'memory_id':entry['id'],'window_id':window_id})
  case={'schema':'p1-maintenance-case-v1','case_id':case_id,'material_kind':'public_visible_reconstruction',
    'task_id':'t_'+sha(case_id.encode())[:20],'task':task,'step_count':step,'initial_bank':bank,
    'entries':current,'prior_presentations':current[:-1],
    'source_windows':list(sources.values()),'entry_sources':refs,
    'observation_dimensions':dimensions,
    'source_manifest':{'archive_url':URLS[zname],'zip_sha256':sha(path.read_bytes()),
      'members':{m:sha(z.read(m)) for m in members.values()},'maintenance_step':step,
      'accepted_event_ids':[e['event_id'] for e in current],
      'transformation':'Initial bank is the public memory_derived view with separator newlines removed and synthetic metadata. Source catalog is reconstructed from matching prior public writes and their visible requests/windows; it is NOT an original production manifest. No future events, evaluations, hidden reasoning or credentials are included.'}}
  return case


def manual(case_id,task,bank,events,dimensions,windows=(),refs=()):
 for category in ('knowledge','procedural','gaps'):
  for entry in bank[category]:
   entry.setdefault('access_count',0);entry.setdefault('last_accessed',None)
 return {'schema':'p1-maintenance-case-v1','case_id':case_id,'material_kind':'manual_control',
   'task_id':'t_'+sha(case_id.encode())[:20],'task':task,'initial_bank':bank,'entries':events,
   'prior_presentations':[],'source_windows':list(windows),'entry_sources':list(refs),'step_count':2,
   'observation_dimensions':dimensions,'source_manifest':{'origin':'Manually authored development control; no production-manifest claim.'}}


def freeze(inputs,output):
 output.mkdir(parents=True,exist_ok=True)
 cases=[public_case(inputs,'01-local-success-scope','p1-lean.zip','runs/sqlite-with-gcov/',14,
     ['Preserve scope of full-path binary success versus PATH claims.','Separate printed claims from the checks actually performed.']),
  public_case(inputs,'02-checkpoint-not-new-install','no-review.zip','visible/',9,
     ['Keep the observed installation attempt count tied to actual commands, not repeated background/checkpoint wording.','Retain useful unresolved conditions without inventing another execution.']),
  public_case(inputs,'03-no-new-result-history','no-review.zip','visible/',17,
     ['Avoid expanding experience into a complete task history when a checkpoint restates already observed results.','Content preservation is evaluated independently of normal new-ID replacement.']),
  public_case(inputs,'04-counterevidence-to-old-claim','p1-lean.zip','runs/fix-ocaml-gc/',28,
     ['Preserve the visible rebuild outcome without adopting Actor claims of a corrected fix as established.','Correct outdated statements while retaining useful attempt history; do not diagnose a new root cause.'])]
 empty={'status':'','knowledge':[],'procedural':[],'gaps':[]}
 events=[{'event_id':key,'step':i+1,'commands':[json.dumps({'id':'cmd-'+key,'tool_name':'query','args':{'workspace':workspace}})],
          'analysis':'Query returned the same count', 'observation':json.dumps({'content':'Actor report',
           'tool_results':[{'tool_use_id':'cmd-'+key,'content':'rows=7'}]})}
         for i,(key,workspace) in enumerate([('exec-a','A'),('exec-b','B')])]
 cases.append(manual('05-distinct-executions-same-output','Collect row counts separately for workspaces A and B.',empty,events,
     ['Different accepted IDs and parameters remain different executions even with matching output.','Do not merge workspace scope by content similarity.']))
 bank={'status':'Workspace B check pending.','knowledge':[{'id':'knownA','content':'Workspace A reports a maximum batch size of 50.','created_at':'manual-control'}],
       'procedural':[],'gaps':[{'id':'gap_b','content':'Workspace B batch size has not yet been observed.','created_at':'manual-control'}]}
 old={'event_id':'older-a','presentation':'historical_visible_event','commands':['query --workspace A --field max_batch'],
      'analysis':'Actor guesses the service may have one global limit',
      'observation':json.dumps({'content':'Actor guess','tool_results':[{'tool_use_id':'query-a','content':'workspace=A max_batch=50'}]})}
 current={'event_id':'new-b','commands':['query --workspace B --field max_batch'],
      'analysis':'Actor says this might replace the old global limit',
      'observation':json.dumps({'content':'Actor interpretation','tool_results':[{'tool_use_id':'query-b','content':'workspace=B max_batch=200'}]})}
 cases.append(manual('06-optional-read-preserve-correct-memory','Collect configuration for workspaces A and B; preserve workspace-specific values.',bank,[current],
     ['Keep a correct older scoped record when a different workspace produces another value.','Read source only if useful; if read, distinguish observations from the older Actor guess.'],
     [{'window_id':'manual_origin','model_input':'Task: collect workspace settings. Raw command query --workspace A --field max_batch; receipt workspace=A max_batch=50. Actor guess: one global limit.', 'visible_events':[old]}],
     [{'memory_id':'knownA','window_id':'manual_origin'}]))
 index={'schema':'p1-source-case-index-v1','status':'frozen_before_real_calls','real_calls':0,
   'cases':[],'notes':'Development material, four public visible reconstructions and two manual controls. Dimensions are withheld from model input. No unique wording answer is supplied. Reads are optional.'}
 for case in cases:
  name=case['case_id']+'.json';dump(output/name,case)
  index['cases'].append({'file':name,'sha256':sha((output/name).read_bytes()),'kind':case['material_kind'],
       'entries':len(case['entries']),'initial_records':sum(len(case['initial_bank'][k]) for k in ('knowledge','procedural','gaps')),
       'reconstructed_source_windows':len(case['source_windows'])})
 dump(output/'INDEX.json',index)
 return index


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args();print(json.dumps(freeze(args.inputs,args.output),ensure_ascii=False))
