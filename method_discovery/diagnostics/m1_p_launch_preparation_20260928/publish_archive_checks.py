"""Copy actual synthetic receipts only; never read profiles/source credentials."""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from prepare_bundle import blob, sha, POLICY_COMMIT, POLICY_PATH


def differences(a, b, path='$'):
    if type(a) is not type(b): return [path]
    if isinstance(a, dict):
        return [p for k in sorted(set(a) | set(b)) for p in
                ([path+'.'+k] if k not in a or k not in b else differences(a[k], b[k], path+'.'+k))]
    if isinstance(a, list):
        if len(a) != len(b): return [path+'.length']
        return [p for i,(x,y) in enumerate(zip(a,b)) for p in differences(x,y,path+'['+str(i)+']')]
    return [] if a == b else [path]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--local-root', required=True); p.add_argument('--output', required=True)
    p.add_argument('--resume-publication', action='store_true', help='repeat only a derived synthetic receipt copy')
    args = p.parse_args(); root = Path(args.local_root).resolve(); out = Path(args.output).resolve()
    if os.name == 'nt':
        root = Path('\\\\?\\' + str(root)); out = Path('\\\\?\\' + str(out))
    out.mkdir(parents=True, exist_ok=args.resume_publication)
    checks = [('normal_m1',2),('normal_p',3),('archive_failure',7),('outer_exception',5),('timeout',6)]
    for name, n in checks:
        source = root / ('archive_check_'+str(n).zfill(2)); target = out / name; target.mkdir(exist_ok=args.resume_publication)
        for rel in ('summary.json','actual_harbor_command.json','retained_inspect.json','cleanup.json',
                    'launch/archive_pause.json','gateway-logs/requests.json'):
            if (source / rel).is_file():
                dest = target / rel; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source / rel, dest)
        trials = list((source / 'launch').glob('*/formal/jobs/*/synthetic-task__*'))
        assert len(trials) == 1
        trial = trials[0]
        record_root=trial.parents[3]
        for rel in ('launch_identity.json','formal/isolated_bundles/pilot-20260929-01/source/pilot_binding.json',
                    'formal/isolated_bundles/pilot-20260929-02/source/pilot_binding.json',
                    'formal/isolated_bundles/pilot-20260929-01/isolation_identity.json',
                    'formal/isolated_bundles/pilot-20260929-02/isolation_identity.json'):
            if (record_root/rel).is_file():
                shutil.copyfile(record_root/rel,target/Path(rel).name)
        for rel in ('config.json','result.json','trial.log'):
            if (trial / rel).is_file(): shutil.copyfile(trial / rel, target / rel)
        shutil.copytree(trial / 'agent', target / 'agent', dirs_exist_ok=args.resume_publication)
        # No mykey, private profiles or gateway configuration is in this projection.
        assert not any(x.name in ('mykey.py','models.local.json','profiles.json') for x in target.rglob('*'))
        summary = json.loads((target / 'summary.json').read_text())
        assert summary['real_model_requests'] == 0
        config=json.loads((target/'config.json').read_text())
        adapter=json.loads((target/'agent/pilot_final_adapter.json').read_text())
        assert config['verifier']['disable'] is True
        assert all(config['agent']['kwargs'][k]==v for k,v in adapter.items())
        environment_file=target/'agent/engineering_env.json'
        if environment_file.is_file():
            environment=json.loads(environment_file.read_text())
            assert environment['GA_MAX_TURNS']=='300' and environment['GA_MONITOR_ARTIFACT_DIR']=='/logs/agent/monitor'
        else:
            # Earlier normal baseline check captured the same real Task env in
            # its actual tool output, before the dedicated file capture existed.
            output=(target/'agent/output.txt').read_text(encoding='utf-8')
            assert 'ENGINEERING_ENV=' in output and '"GA_MAX_TURNS": "300"' in output

    # Preserve the two earlier engineering failures, without copying the first
    # check's irrelevant image workspace/checkpoint expansion.
    for n in (1,4):
        source = root / ('archive_check_'+str(n).zfill(2))
        target = out / 'earlier_engineering_failures' / str(n); target.mkdir(parents=True,exist_ok=args.resume_publication)
        for rel in ('actual_harbor_command.json','launch/archive_pause.json','gateway-logs/requests.json'):
            if (source/rel).is_file():
                dest=target/rel; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source/rel,dest)
        trial=next((source/'launch').glob('*/formal/jobs/*/synthetic-task__*'))
        for rel in ('config.json','result.json','trial.log','agent/pilot_archive_failure.json','agent/pilot_archive_receipt.json'):
            if (trial/rel).is_file():
                dest=target/rel; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(trial/rel,dest)
        if n == 4:
            failure=json.loads((source/'launch/archive_pause.json').read_text())
            project=failure['session_id'].lower()
            assert project.startswith('synthetic-task__') and project.endswith('__env')
            ids=subprocess.check_output(['docker','ps','-a','--filter',
                'label=com.docker.compose.project='+project,'--format','{{.ID}}']).decode().split()
            if ids:
                inspection=subprocess.check_output(['docker','inspect',*ids])
                objects=json.loads(inspection)
                assert all(o['Config']['Labels']['com.docker.compose.project']==project for o in objects)
                (target/'retained_inspect.json').write_bytes(inspection)
                cleanup=subprocess.run(['docker','rm','-f',*ids],capture_output=True)
                (target/'cleanup.json').write_text(json.dumps(dict(ids=ids,project=project,
                    returncode=cleanup.returncode,stdout=cleanup.stdout.decode(),stderr=cleanup.stderr.decode()),indent=2))
                assert cleanup.returncode==0

    body = blob(POLICY_COMMIT, POLICY_PATH).decode().strip()
    requests = [json.loads((out / name / 'gateway-logs/requests.json').read_text()) for name in ('normal_m1','normal_p')]
    captures = [[r['payload'] for r in group if r['role']=='supervisor'] for group in requests]
    mappings = []
    def normalize(payload):
        obj = copy.deepcopy(payload)
        # Only the exact generated original-task filename identity; no general
        # path rewriting, no removal of semantic state/evidence/history.
        def visit(x):
            if isinstance(x,str):
                ids = re.findall(r'/app/\.monitor_original_task_[0-9a-f]{32}\.txt',x)
                for ident in ids:
                    mappings.append({'original':ident,'canonical':'/app/.monitor_original_task_<id>.txt'})
                    x=x.replace(ident,'/app/.monitor_original_task_<id>.txt')
                return x
            if isinstance(x,list): return [visit(v) for v in x]
            if isinstance(x,dict): return {k:visit(v) for k,v in x.items()}
            return x
        return visit(obj)
    a,b = captures[0][0],captures[1][0]
    normalized_a,normalized_b = normalize(a),normalize(b)
    assert body not in normalized_a['system'] and normalized_b['system'].count(body)==1
    normalized_b['system']=normalized_b['system'].replace('\n\n'+body,'',1)
    delta=differences(normalized_a,normalized_b)
    assert not delta, delta
    for group, count in zip(captures,(0,1)):
        assert all(r['system'].count(body)==count for r in group)
        assert all(r['tools']==a['tools'] for r in group)
    # Also verify normal cleanup against actual Docker project labels in lowercase.
    cleanup_checks=[]
    for name in ('normal_m1','normal_p','outer_exception','timeout'):
        receipt=json.loads((out/name/'agent/pilot_archive_receipt.json').read_text())
        remaining=subprocess.check_output(['docker','ps','-a','--filter',
             'label=com.docker.compose.project='+receipt['session_id'].lower(),'--format','{{.ID}}']).decode().strip()
        assert not remaining
        cleanup_checks.append({'case':name,'project':receipt['session_id'].lower(),'remaining_container_ids':remaining})
    report=dict(first_request_raw_difference_paths=differences(a,b),
        declared_identity_mappings=mappings, first_request_remaining_differences_after_policy_and_identity_mapping=delta,
        every_supervisor_request_policy_count_checked=True, tools_equal_every_request=True,
        actual_cleanup_checks=cleanup_checks, actual_model_requests=0,
        limitation='Asynchronous later history is archived, not erased or asserted identical; fake actions are not model capability evidence.')
    (out/'comparison.json').write_text(json.dumps(report,indent=2))
    unit=subprocess.run([str(Path(__import__('sys').executable)), '-m', 'unittest', 'discover',
        '-s',str(Path(__file__).resolve().parent),'-p','test_archive_pause.py','-v'],capture_output=True)
    (out/'unit_checks.json').write_text(json.dumps(dict(command=unit.args,returncode=unit.returncode,
        stdout=unit.stdout.decode('utf-8','replace'),stderr=unit.stderr.decode('utf-8','replace')),indent=2))
    assert unit.returncode==0
    files=[dict(path=f.relative_to(out).as_posix(),bytes=f.stat().st_size,sha256=sha(f.read_bytes()))
           for f in sorted(out.rglob('*')) if f.is_file() and f.name != 'file_manifest.json']
    (out/'file_manifest.json').write_text(json.dumps(files,indent=2))
    print(json.dumps({'copied_cases':len(checks),'files':len(files),'comparison':report},indent=2))


if __name__ == '__main__': main()
