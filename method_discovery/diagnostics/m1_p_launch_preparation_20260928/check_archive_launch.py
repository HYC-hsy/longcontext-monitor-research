"""Finite synthetic E2E check through launch_pilot -> run_proof -> Harbor.

Fake upstream, network-none Docker, no benchmark/verifier or real model. Test
seams replace only task selection, preflight, telemetry sink and final scoring.
The actual launcher, kwargs, bundle, Harbor CLI, adapter, Task and Monitor run.
Each invocation must be in a fresh process (pinned runner import constraint).
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import launch_pilot
from prepare_bundle import ROOT, HERE, M1, TASK, POLICY_COMMIT, POLICY_PATH, blob, sha

PYHOME = 'cpython-3.12.12-linux-x86_64-gnu'
PYTHON = '/opt/m4-runtime/python/' + PYHOME + '/bin/python3.12'
IMAGE = 'sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--supervisor-source', required=True)
    parser.add_argument('--policy', action='store_true')
    parser.add_argument('--failure', choices=['none', 'archive', 'outer', 'timeout'], default='none')
    args = parser.parse_args()
    out = Path(args.output_root).resolve(); out.mkdir(parents=True, exist_ok=False)
    fixture = out / 'synthetic-task'; fixture.mkdir()
    workspace = out / 'synthetic-workspace'; workspace.mkdir()
    (fixture / 'environment').mkdir()
    (fixture / 'instruction.md').write_text('Engineering fixture only: print the runtime configuration and finish. No project task or evaluation.\n')
    (fixture / 'task.toml').write_text('version="1"\n[agent]\ntimeout_sec=120\n[environment]\ndocker_image="' + IMAGE + '"\ncpus=2\nmemory_mb=4096\n')
    profiles = launch_pilot.common_profiles()
    for cfg in profiles.values(): cfg.update(apikey='virtual-engineering-only', apibase='https://offline.invalid/v1')
    (out / 'profiles.json').write_text(json.dumps(profiles))
    record = 'kitex-m1-p' if args.policy else 'kitex-m1'
    auth = dict(authorization=True, records=[record], supervisor_commit=M1, task_commit=TASK,
                policy_sha256=sha(blob(POLICY_COMMIT, POLICY_PATH)), launcher_sha256=sha(Path(launch_pilot.__file__).read_bytes()),
                engineering_fake_only=True)
    (out / 'authorization.json').write_text(json.dumps(auth))
    original_load = launch_pilot.load_frozen_roadmap_runner
    original_bind = launch_pilot.bind_roadmap_builder

    def load(directory):
        runner, imports = original_load(directory)
        runner.preflight = lambda *a: dict(model={'model':'claude-opus-4-8','effective_llm_no':0},
            runtime={'python_home':PYHOME}, generic_agent={'source_sha256':'engineering-synthetic-preflight'})
        runner.materialize_execution_task = lambda *a: fixture
        runner.proposal_row = lambda *a: {'agent_timeout_sec':120}
        runner.m4.start_collector = lambda: None
        runner.m4.stop_collector = lambda: None
        original_run = runner.m4.run
        def run(command, **kwargs):
            if command[0].lower().endswith('harbor.exe'):
                command = command + ['--disable-verification']
                # Bounded synthetic run; production launcher still has 7200.
                i = command.index('--agent-timeout-multiplier'); command[i+1] = '1'
                if args.failure == 'timeout': command[i+1] = '0.25'
                for i, value in enumerate(command):
                    if value.startswith('timeout_sec='): command[i] = 'timeout_sec=120'
                if args.failure in ('archive', 'outer'):
                    bench = Path(directory) / 'long_context_bench'
                    (bench / 'adapters/synthetic_failure_agent.py').write_text(
                        'from adapters.pilot_archive_agent import PilotArchiveAgent\n'
                        'class SyntheticFailureAgent(PilotArchiveAgent):\n' + (
                        ' async def _pilot_archive(self, environment):\n  await super()._pilot_archive(environment)\n  raise OSError("synthetic archive failure before cleanup")\n'
                        if args.failure == 'archive' else
                        ' async def run(self, instruction, environment, context):\n  await super().run(instruction, environment, context)\n  raise RuntimeError("synthetic outer exception after native Task termination")\n'))
                    i = command.index('--agent'); command[i+1] = 'adapters.synthetic_failure_agent:SyntheticFailureAgent'
                (out / 'actual_harbor_command.json').write_text(json.dumps(command, indent=2))
            return original_run(command, **kwargs)
        runner.m4.run = run
        def finalize(*a):
            configs = list(runner.JOBS_ROOT.rglob('config.json'))
            results = list(runner.JOBS_ROOT.rglob('result.json'))
            return dict(engineering_only=True, configs=[str(p) for p in configs], results=[str(p) for p in results])
        runner._finalize_proof = finalize
        return runner, imports

    def bind(runner, **kwargs):
        original_bind(runner, **kwargs)
        original_builder = runner.build_bundle
        def builder(*a, **kw):
            source, compose = original_builder(*a, **kw)
            config = json.loads(compose.read_text())
            config['services']['main'].setdefault('volumes', []).append(f'{workspace.as_posix()}:/app:rw')
            gateway = config['services']['model-gateway']
            logs = out / 'gateway-logs'; logs.mkdir(exist_ok=True)
            gateway.update(network_mode='none', entrypoint=[PYTHON, '/checks/check_archive_gateway.py'])
            if args.failure == 'timeout': gateway['environment']['ENGINEERING_TIMEOUT'] = '1'
            gateway['volumes'].extend([f'{HERE.as_posix()}:/checks:ro', f'{logs.as_posix()}:/gateway-logs:rw'])
            compose.write_text(json.dumps(config, indent=2))
            return source, compose
        runner.build_bundle = builder

    launch_pilot.load_frozen_roadmap_runner = load
    launch_pilot.bind_roadmap_builder = bind
    sys.argv = ['launch_pilot.py','--record',record,'--supervisor-source',args.supervisor_source,
                '--output-root',str(out / 'launch'),'--execute','--authorization',str(out / 'authorization.json'),
                '--profiles',str(out / 'profiles.json')]
    launch_pilot.main()
    host = out / 'launch' / record
    adapter_files = list(host.rglob('pilot_final_adapter.json'))
    assert len(adapter_files) == 1
    adapter = json.loads(adapter_files[0].read_text())
    assert adapter == dict(max_turns=300, monitor_enabled=True, monitor_config='claude_monitor_opus48',
                           llm_config_name='native_claude_cc_vibe_opus48', baseline_condition='original')
    configs = [json.loads(p.read_text()) for p in host.glob('formal/jobs/*/synthetic-task__*/config.json')]
    assert len(configs) == 1 and configs[0]['verifier']['disable'] is True
    for key,value in adapter.items(): assert configs[0]['agent']['kwargs'][key] == value
    env_files = list(host.rglob('engineering_env.json'))
    assert len(env_files) == 1, 'actual Task tool did not save subprocess environment'
    environment = json.loads(env_files[0].read_text())
    assert environment == dict(GA_MAX_TURNS='300', GA_LLM_CONFIG_NAME='native_claude_cc_vibe_opus48',
        GA_MONITOR_ENABLED='1', GA_MONITOR_CONFIG='claude_monitor_opus48',
        GA_MONITOR_ARTIFACT_DIR='/logs/agent/monitor', GA_BASELINE_CONDITION='original')
    requests = json.loads((out / 'gateway-logs/requests.json').read_text())
    assert {'task','supervisor'} == {r['role'] for r in requests}
    body = blob(POLICY_COMMIT, POLICY_PATH).decode().strip()
    for r in requests:
        if r['role'] == 'supervisor':
            assert r['payload']['system'].count(body) == int(args.policy)
    receipts = list(host.rglob('pilot_archive_receipt.json'))
    failures = list(host.rglob('pilot_archive_failure.json'))
    if args.failure == 'archive':
        assert failures and not receipts and (out / 'launch/archive_pause.json').is_file()
        session = json.loads(failures[0].read_text())['session_id']
        retained = subprocess.check_output(['docker','ps','-a','--filter','label=com.docker.compose.project='+session.lower(),'--format','{{.ID}}']).decode().split()
        assert retained, 'archive failure incorrectly deleted containers'
        # Save actual retained originals/inspect before scoped engineering cleanup.
        (out / 'retained_inspect.json').write_bytes(subprocess.check_output(['docker','inspect',*retained]))
        (out / 'cleanup.json').write_text(json.dumps({'engineering_container_ids':retained,
             'result':subprocess.run(['docker','rm','-f',*retained],capture_output=True).returncode}))
    else:
        assert receipts and not failures
        receipt = json.loads(receipts[0].read_text())
        for f in receipt['files']:
            path = receipts[0].parent / f['path']
            assert path.is_file() and sha(path.read_bytes()) == f['sha256']
        remaining = subprocess.check_output(['docker','ps','-a','--filter','label=com.docker.compose.project='+receipt['session_id'].lower(),'--format','{{.ID}}']).decode().strip()
        assert not remaining, 'normal cleanup incomplete'
    summary = dict(engineering_only=True, fake_provider_requests=len(requests), real_model_requests=0,
        network='main and fake gateway network=none; fake HTTPS permits offline.invalid only',
        actual_adapter=adapter, archive_receipts=[str(p.relative_to(out)) for p in receipts],
        archive_failures=[str(p.relative_to(out)) for p in failures], policy_enabled=args.policy,
        failure_injection=args.failure, assertions='executed, not semantic assessment')
    (out / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()
