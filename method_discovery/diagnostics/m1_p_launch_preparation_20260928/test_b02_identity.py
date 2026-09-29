"""Finite B02 identity test. No Docker, provider request or task execution."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import launch_pilot as launch
from prepare_bundle import HERE, ROOT, M1, TASK, POLICY_COMMIT, POLICY_PATH, blob, sha


def authorization():
    return dict(authorization=True, batch_id=launch.BATCH_ID, records=list(launch.BATCH_RUNS),
        execution_commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD']).decode().strip(),
        record_run_ids=launch.BATCH_RUNS, supervisor_commit=M1, task_commit=TASK,
        policy_sha256=sha(blob(POLICY_COMMIT,POLICY_PATH)),
        launcher_sha256=sha(Path(launch.__file__).read_bytes()),
        archive_adapter_sha256=sha((HERE/'pilot_archive_agent.py').read_bytes()))


def child(record, output):
    root=Path(output); root.mkdir()
    auth=root/'auth.json'; auth.write_text(json.dumps(authorization()))
    profiles=launch.common_profiles()
    for cfg in profiles.values(): cfg.update(apikey='virtual-only',apibase='https://offline.invalid/v1')
    (root/'profiles.json').write_text(json.dumps(profiles))
    original_load=launch.load_frozen_roadmap_runner
    original_bind=launch.bind_roadmap_builder
    receipt={}
    def load(directory):
        runner,imports=original_load(directory)
        def boundary(source,run_id,llm_no,seconds,task):
            assert run_id==launch.BATCH_RUNS[record] and seconds==7200 and task=='ktx-0.13.0-roadmap'
            kwargs=runner.stage4_agent_kwargs()
            assert kwargs['max_turns']==300 and kwargs['monitor_enabled'] is True
            assert kwargs['monitor_config']=='claude_monitor_opus48'
            assert kwargs['llm_config_name']=='native_claude_cc_vibe_opus48'
            assert kwargs['baseline_condition']=='original'
            assert 'pilot_archive_pause_path' in kwargs
            receipt.update(run_proof_args=[source,run_id,llm_no,seconds,task],final_kwargs=kwargs,
                real_provider_requests=0,source_imports=imports)
            return dict(engineering_only=True)
        runner.run_proof=boundary
        return runner,imports
    def bind(runner,**kwargs):
        assert kwargs['policy']==(record=='kitex-m1-p') and kwargs['budget_enabled'] is False
        assert kwargs['historical_config'] is True
        receipt['policy_enabled']=kwargs['policy']
        return original_bind(runner,**kwargs)
    argv=['launch_pilot.py','--batch-id',launch.BATCH_ID,'--run-id',launch.BATCH_RUNS[record],
        '--record',record,'--supervisor-source',str(ROOT.parent/'LongContext_m1_frozen'),
        '--output-root',str(root/'output'),'--execute','--authorization',str(auth),
        '--profiles',str(root/'profiles.json')]
    with patch.object(launch,'load_frozen_roadmap_runner',load), patch.object(launch,'bind_roadmap_builder',bind),patch('sys.argv',argv):
        launch.main()
    identity=json.loads((root/'output'/record/'launch_identity.json').read_text())
    assert identity['run_id']==launch.BATCH_RUNS[record] and identity['batch_id']==launch.BATCH_ID
    (root/'receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))


class IdentityTests(unittest.TestCase):
    def test_both_mappings_reach_final_pinned_runner_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            for record in launch.BATCH_RUNS:
                result=subprocess.run([sys.executable,__file__,'--child',record,str(Path(temp)/record)],capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
                receipt=json.loads((Path(temp)/record/'receipt.json').read_text())
                self.assertEqual(receipt['real_provider_requests'],0)
    def test_old_id_wrong_mapping_and_authorization_rejected(self):
        for batch,record,run in [(launch.BATCH_ID,'kitex-m1','pilot-20260929-01'),
                                (launch.BATCH_ID,'kitex-m1',launch.BATCH_RUNS['kitex-m1-p']),
                                ('old-batch','kitex-m1',launch.BATCH_RUNS['kitex-m1'])]:
            with self.assertRaises(RuntimeError): launch.validate_identity(batch,record,run)
        with tempfile.TemporaryDirectory() as temp:
            auth=authorization(); auth['record_run_ids']={}; path=Path(temp)/'auth.json'; path.write_text(json.dumps(auth))
            with self.assertRaises(RuntimeError): launch.authorize(path,'kitex-m1',launch.BATCH_ID,launch.BATCH_RUNS['kitex-m1'])
    def test_archive_pause_still_precedes_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'auth.json').write_text(json.dumps(authorization())); (root/'archive_pause.json').write_text('{}')
            argv=['launch_pilot.py','--batch-id',launch.BATCH_ID,'--run-id',launch.BATCH_RUNS['kitex-m1'],
                '--record','kitex-m1','--supervisor-source',str(root),'--output-root',str(root),
                '--execute','--authorization',str(root/'auth.json'),'--profiles',str(root/'absent.json')]
            with patch('sys.argv',argv):
                with self.assertRaisesRegex(RuntimeError,'prior archive failure'): launch.main()


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child': child(sys.argv[2],sys.argv[3])
    else: unittest.main()
