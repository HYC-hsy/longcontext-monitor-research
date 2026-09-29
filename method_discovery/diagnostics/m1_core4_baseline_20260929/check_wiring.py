"""Finite no-model checks for this batch's new identity and CLAW archive binding."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import launch_core4 as launch
from prepare_bundle import prepare
from sphinx_entry import install_archive_and_environment, REQUIRED


def child(record, root):
    root = Path(root)
    root.mkdir()
    auth = dict(authorization=True, batch_id=launch.BATCH, records=list(launch.CASES),
        record_run_ids=launch.RUNS, supervisor_commit=launch.M1, task_commit=launch.TASK,
        execution_commit=subprocess.check_output(['git', '-C', str(launch.ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        execution_files=launch.identities(), policy_enabled=False)
    (root / 'auth.json').write_text(json.dumps(auth))
    cfg = launch.native.common_profiles()
    for profile in cfg.values():
        profile.update(apikey='offline-virtual-only', apibase='https://offline.invalid')
    (root / 'profiles.json').write_text(json.dumps(cfg))
    receipt = {}
    original = launch.native.load_frozen_roadmap_runner
    def load(directory):
        runner, imports = original(directory)
        def boundary(source, run, llm, seconds, task):
            assert source == 'roadmapbench' and seconds == 7200
            assert run == launch.RUNS[record] and task == launch.CASES[record][0].split(':')[1]
            kwargs = runner.stage4_agent_kwargs()
            assert kwargs['max_turns'] == 300 and kwargs['monitor_enabled'] is True
            assert kwargs['llm_config_name'] == 'native_claude_cc_vibe_opus48'
            assert kwargs['monitor_config'] == 'claude_monitor_opus48'
            assert kwargs['baseline_condition'] == 'original'
            receipt.update(run_proof_args=[source, run, llm, seconds, task], kwargs=kwargs, imports=imports)
            return dict(engineering_only=True)
        runner.run_proof = boundary
        return runner, imports
    argv = ['launch_core4.py', '--batch-id', launch.BATCH, '--record', record,
        '--run-id', launch.RUNS[record], '--supervisor-source', str(launch.ROOT.parent / 'LongContext_m1_frozen'),
        '--output-root', str(root / 'output'), '--execute', '--authorization', str(root / 'auth.json'),
        '--profiles', str(root / 'profiles.json')]
    with patch.object(launch.native, 'load_frozen_roadmap_runner', load), patch('sys.argv', argv):
        launch.main()
    assert json.loads((root / 'output' / record / 'launch_identity.json').read_text())['policy_enabled'] is False
    print(json.dumps(receipt))


def main():
    out = launch.HERE / 'wiring_receipt.json'
    receipts = []
    with tempfile.TemporaryDirectory(prefix='core4-wiring-') as temp:
        root = Path(temp)
        for record in ('fyne-m1', 'kitex-m1'):
            result = subprocess.run([sys.executable, __file__, '--child', record, str(root / record)], capture_output=True)
            receipts.append(dict(check=record + '-final-runner-boundary', returncode=result.returncode,
                stdout=result.stdout.decode('utf-8', 'replace'), stderr=result.stderr.decode('utf-8', 'replace')))
            if result.returncode:
                raise AssertionError(receipts[-1])
        for batch, record, run in [(launch.BATCH, 'kitex-m1', 'pilot-b02-20260929-01'),
                ('old', 'fyne-m1', launch.RUNS['fyne-m1']),
                (launch.BATCH, 'sphinx-m1', launch.RUNS['fyne-m1'])]:
            try:
                launch.validate(batch, record, run)
            except RuntimeError:
                pass
            else:
                raise AssertionError('wrong identity accepted')
        # Use the same prepared source and actual frozen worker/provider fake-send seam.
        bundle = root / 'bundle'
        cfg = launch.native.common_profiles()
        for profile in cfg.values():
            profile.update(apikey='offline-virtual-only', apibase='https://offline.invalid')
        copied, _ = prepare(bundle, launch.ROOT.parent / 'LongContext_m1_frozen', False,
            budget_enabled=False, historical_config=True, role_profiles=cfg)
        capture = launch.HERE / 'no_model_request_capture.json'
        result = subprocess.run([sys.executable, '-I', str(launch.PILOT / 'capture_worker.py'),
            '--bundle', str(bundle), '--output', str(capture)], capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr.decode('utf-8', 'replace'))
        actual = json.loads(capture.read_text())
        assert actual['actual_model_requests'] == 0 and actual['effective_config']['monitor_dcec'] is True
        binding = json.loads((copied / 'pilot_binding.json').read_text())
        assert binding['monitor_commit'] == launch.M1 and not binding['policy_enabled'] and not binding['budget_enabled']
        assert not (copied / 'monitor_agent_core/dcec_control_slot.py').exists()
        receipts.append(dict(check='exact-M1-bundle-native-worker-fake-transport', captured_requests=len(actual['requests']),
            real_model_requests=actual['actual_model_requests'], imported_modules=actual['modules'], policy_enabled=False))

        # Actual local archive files; mock only container inspection, not file checks.
        artifacts = root / 'sphinx' / 'sphinx-doc__sphinx-8551'
        artifacts.mkdir(parents=True)
        events = []
        class Base:
            def __init__(self):
                self.max_turns = 300
                self.model_identity = {'model': 'claude-opus-4-8'}
                self.artifacts_root = artifacts.parent
            def post_container_start(self, workspace):
                pass
            def build_exec_command(self, *a, **kw):
                env = {'GA_MAX_TURNS': '300', 'GA_LLM_CONFIG_NAME': 'native_claude_cc_vibe_opus48',
                    'GA_MONITOR_ENABLED': '1', 'GA_MONITOR_CONFIG': 'claude_monitor_opus48',
                    'GA_MONITOR_DCEC': '1', 'GA_MONITOR_DCEC_WORKING_CHARS': '4000',
                    'GA_MONITOR_ARTIFACT_DIR': '/opt/m2-artifacts/monitor'}
                command = ['docker', 'exec']
                for k, v in env.items():
                    command += ['-e', k + '=' + v]
                return command + ['synthetic-container', 'python', 'agentmain.py']
            def send_task(self, prompt, *a, **kw):
                events.append(prompt)
                return 'synthetic-result'
        module = SimpleNamespace(M2GenericAgentAdapter=Base)
        install_archive_and_environment(module, root, launch.RUNS['sphinx-m1'])
        adapter = module.M2GenericAgentAdapter()
        workspace = SimpleNamespace(container_name='synthetic-container', cleanup=lambda: events.append('deleted'))
        image = 'sha256:77f476927410992943a8d2744aea86b3e0c50d8773b61e56ebba9dd0fd4b9db1'
        with patch('sphinx_entry.subprocess.check_output', return_value=json.dumps([{
                'Image': image, 'Mounts': [], 'HostConfig': {}}]).encode()):
            adapter.post_container_start(workspace)
        adapter.build_exec_command('synthetic-agent', 'synthetic-container', 'sphinx-doc__sphinx-8551')
        adapter.send_task('Synthetic public task.\n')
        assert events[0].endswith((launch.HERE / 'SPHINX_ENVIRONMENT.txt').read_text())
        try:
            workspace.cleanup()
        except RuntimeError:
            pass
        else:
            raise AssertionError('missing originals did not block cleanup')
        assert 'deleted' not in events and (root / 'archive_pause.json').exists()
        for rel in REQUIRED:
            p = artifacts / 'monitor' / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('Synthetic engineering artifact, not scientific raw.\n')
        workspace.cleanup()
        assert events[-1] == 'deleted' and (artifacts / 'archive_before_cleanup.json').exists()
        receipts.append(dict(check='Sphinx-final-environment-neutral-note-archive-success-and-failure',
            passed=True, container_calls_mocked=True, real_file_validation=True))
    out.write_text(json.dumps(dict(checks=receipts, real_model_requests=0,
        synthetic_fixture_only=True, limitations='No Sphinx benchmark execution in these checks; existing isolation adapter reused.'), indent=2), encoding='utf-8')
    print('Finite core4 wiring checks passed; no real provider requests.')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--child':
        child(sys.argv[2], sys.argv[3])
    else:
        main()
