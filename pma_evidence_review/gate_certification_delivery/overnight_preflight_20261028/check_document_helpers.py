from pathlib import Path
import json,sys,tempfile,hashlib,subprocess
from unittest.mock import patch
import importlib
s=Path('pma_evidence_review/gate_certification_delivery/OVERNIGHT_HANDOFF.md').read_text()
prep=s.split("$PrepareAndAuthorize=@'\n")[1].split("\n'@",1)[0]
post=s.split("  @'\nimport json, pathlib, sys\n")[1].split("\n'@",1)[0]
post='import json, pathlib, sys\n'+post
compile(prep,'prepare_authorize','exec');compile(post,'postcheck','exec')
base='method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013'
sr=importlib.import_module(base+'.single_run');gc=importlib.import_module(base+'.gate_certification');cfg=importlib.import_module(base+'.citation_gate_config')
repo=Path.cwd();head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
checks=[]
with tempfile.TemporaryDirectory() as td:
 root=Path(td);out=root/'slot';policy=root/'policy.json';policy.write_text(json.dumps({'agent_timeout':'uncapped','task_turns':'uncapped','verifier_timeout':'official'}))
 def fake_prepare(a):
  assert a.evaluation_bootstrap_protocol=='download_retry_v1' and a.evaluation_download_retry=={'max_attempts':3}
  out.mkdir();row={'order':1,'task':a.task,'repeat':1,'condition':'B','research_candidate':'pma_gap_evidence_v1'}
  config={'research_candidate':row['research_candidate'],'citation_review_gate':a.citation_review_gate,'runtime_policy':{'requested':a.runtime_policy},'evaluation_bootstrap_protocol':a.evaluation_bootstrap_protocol,'evaluation_download_retry':a.evaluation_download_retry,'citation_gate_source_sha256':{p:hashlib.sha256((repo/p).read_bytes()).hexdigest()for p in cfg.gate_source_paths()}}
  h=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  m={'schema':'pma-ga-live-manifest-v5','execution_authorized':False,'planned_order':[row],'config':config,'config_sha256':h,'assets':{a.task:{}}}
  mp=out/'manifest.json';mp.write_text(json.dumps(m));identity={'run_id':'r','run_root':str(out/'runs/r'),'output_root':str(out/'runs'),'manifest_sha256':hashlib.sha256(mp.read_bytes()).hexdigest(),'execution_authorized':False};(out/'run_identity.json').write_text(json.dumps(identity));return identity
 with patch.object(sys,'argv',['helper',str(repo),str(out),'sqlite-with-gcov','gate-only','unused','unused','unused','unused',str(policy),head]),patch.object(sr,'prepare',side_effect=fake_prepare),patch.object(gc,'require_launch_certificate') as cert:
  exec(compile(prep,'prepare_authorize','exec'),{})
  assert cert.call_args.kwargs=={'fixture':False}
 checks.append('authorization helper actual validate_plan/source-hash checks passed; asset preparation/certificate IO mocked, not native certification')
 grant=json.loads((out/'authorization.json').read_text());assert grant['zero_model_fixture_only'] is False
 (out/'authorization.json').unlink()
 i=json.loads((out/'run_identity.json').read_text());rr=Path(i['run_root']);(rr/'archive').mkdir(parents=True)
 status={'run_id':'r','zero_model_fixture_only':False,'cleanup_confirmed':True,'remaining_containers':[],'cleanup_errors':[],'owned_volume_clearance':{'status':'clean','remaining':[]},'sidecar_clearance':{'clean':True},'native_result':{'status':'native_recorded','rewards':{'reward':0.0}},'native_script_observed':True,'native_reports_checked':True}
 def records(st):
  (rr/'archive/live_result.json').write_text(json.dumps(st));(out/'batch_result.json').write_text(json.dumps({'stop_reason':None,'arms':[{'run_id':'r','disposition':'completed','status':st}]}))
 records(status)
 with patch.object(sys,'argv',['post',str(out)]):exec(compile(post,'postcheck','exec'),{})
 checks.append('postcheck accepts recorded reward=0 with clean terminal evidence')
 for key,val in [('cleanup_confirmed',False),('native_reports_checked',False)]:
  changed={**status,key:val};records(changed)
  with patch.object(sys,'argv',['post',str(out)]):
   try:exec(compile(post,'postcheck','exec'),{})
   except RuntimeError:checks.append('postcheck rejects '+key)
   else:raise AssertionError(key)
print(json.dumps({'checks':checks,'real_calls':0,'Task_starts':0,'native_lifecycles':0},indent=2))
