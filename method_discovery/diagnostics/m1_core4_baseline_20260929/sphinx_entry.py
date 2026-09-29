"""Parameter binding around the existing isolated CLAW-SWE run/evaluate path."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from launch_core4 import HERE, ROOT, PILOT, BATCH, M1, TASK, native
from prepare_bundle import export, prepare, sha

INSTANCE = 'sphinx-doc__sphinx-8551'
IMAGE = 'sha256:77f476927410992943a8d2744aea86b3e0c50d8773b61e56ebba9dd0fd4b9db1'
GATEWAY = 'sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171'
REQUIRED = ['monitor_private/working.md', 'monitor_private/audit/dialogue.jsonl',
    'monitor_private/audit/progress.jsonl', 'monitor_private/audit/reviews.jsonl',
    'monitor_private/audit/provider_history.json', 'monitor_private/audit/request_attempts.jsonl',
    'monitor_private/audit/provider_usage.jsonl', 'runtime_receipts.jsonl']


def verify_archive(root):
    root = Path(root)
    missing = [p for p in REQUIRED if not (root / 'monitor' / p).is_file()]
    if missing:
        raise RuntimeError('Supervisor originals absent before cleanup: ' + ', '.join(missing))
    files = [dict(path=p.relative_to(root).as_posix(), bytes=p.stat().st_size,
        sha256=sha(p.read_bytes())) for p in sorted(root.rglob('*')) if p.is_file()
        and p.name != 'archive_before_cleanup.json']
    (root / 'archive_before_cleanup.json').write_text(json.dumps(dict(
        status='host_originals_readable_before_cleanup', files=files), indent=2), encoding='utf-8')
    return files


def install_archive_and_environment(module, output, run_id, profile_path=None):
    base = module.M2GenericAgentAdapter
    note = (HERE / 'SPHINX_ENVIRONMENT.txt').read_text(encoding='utf-8')

    class Core4Adapter(base):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            if self.max_turns != 300 or self.model_identity['model'] != 'claude-opus-4-8':
                raise RuntimeError('final Sphinx Task configuration mismatch')

        def container_run_args(self, instance_id):
            command = super().container_run_args(instance_id)
            if profile_path is None:
                raise RuntimeError('explicit isolated Supervisor profile mount missing')
            return command + ['--mount', f'type=bind,src={Path(profile_path).resolve()},dst=/pilot-config/models.json,readonly']

        def post_container_start(self, workspace):
            original_cleanup = workspace.cleanup
            self._core4_task_started = False
            artifacts = self.artifacts_root / INSTANCE
            def cleanup():
                if self._core4_task_started:
                    try:
                        verify_archive(artifacts)
                    except BaseException as error:
                        pause = Path(output) / 'archive_pause.json'
                        pause.write_text(json.dumps(dict(run_id=run_id, container=workspace.container_name,
                            error_type=type(error).__name__, error=str(error),
                            status='archive_failure_container_retained'), indent=2), encoding='utf-8')
                        raise
                return original_cleanup()
            workspace.cleanup = cleanup
            super().post_container_start(workspace)
            inspected = json.loads(subprocess.check_output(['docker', 'inspect', workspace.container_name]))[0]
            if inspected['Image'] != IMAGE:
                raise RuntimeError('Sphinx actual container image mismatch')
            (artifacts / 'container_identity.json').write_text(json.dumps(dict(image=inspected['Image'],
                mounts=inspected['Mounts'], host_config=inspected['HostConfig'], run_id=run_id), indent=2), encoding='utf-8')

        def build_exec_command(self, *a, **kw):
            command = super().build_exec_command(*a, **kw)
            # Explicit model configuration is the existing native adapter interface.
            container = a[1] if len(a) > 1 else kw['container_name']
            index = command.index(container)
            command[index:index] = ['-e', 'MONITOR_CONFIG_FILE=/pilot-config/models.json']
            values = [command[i + 1] for i, value in enumerate(command[:-1]) if value == '-e']
            env = dict(value.split('=', 1) for value in values)
            required = {'GA_MAX_TURNS': '300', 'GA_LLM_CONFIG_NAME': 'native_claude_cc_vibe_opus48',
                'GA_MONITOR_ENABLED': '1', 'GA_MONITOR_CONFIG': 'claude_monitor_opus48',
                'GA_MONITOR_DCEC': '1', 'GA_MONITOR_DCEC_WORKING_CHARS': '4000',
                'GA_MONITOR_ARTIFACT_DIR': '/opt/m2-artifacts/monitor'}
            if any(env.get(k) != v for k, v in required.items()):
                raise RuntimeError('final Sphinx execution environment mismatch')
            path = self.artifacts_root / INSTANCE / 'final_adapter_environment.json'
            path.write_text(json.dumps(dict(run_id=run_id, max_turns=self.max_turns,
                environment=env, command=command), indent=2), encoding='utf-8')
            return command

        def send_task(self, prompt, *a, **kw):
            self._core4_task_started = True
            # Both Task and native Monitor receive the same neutral environment text.
            return super().send_task(prompt + note, *a, **kw)

    module.M2GenericAgentAdapter = Core4Adapter


def execute(args, profiles, *, prepare_only=False):
    dest = Path(args.output_root).resolve() / args.record
    dest.mkdir(parents=True, exist_ok=False)
    helper_path = ROOT / 'method_discovery/run_dcec_v1_claw_swe_generalization.py'
    spec = importlib.util.spec_from_file_location('core4_historical_isolation', helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    launcher = dest / 'launcher'
    export(TASK, 'long_context_bench/scripts', launcher)
    bench = launcher / 'long_context_bench'
    shutil.copyfile(HERE / 'launch_substrate/run_claw_swe_m3.py', bench / 'scripts/run_claw_swe_m3.py')
    collector = PILOT / 'launch_substrate_originals/long_context_bench/config/otel-collector-m2.yaml'
    (bench / 'config').mkdir()
    shutil.copyfile(collector, bench / 'config/otel-collector-m2.yaml')
    runtime = ROOT / 'bench_runtime/m2/linux'
    home = helper.python_home()
    copied, compose = prepare(dest / 'isolated_bundle', args.supervisor_source, False,
        budget_enabled=False, historical_config=True, role_profiles=profiles,
        record_id=args.record, runtime_source=runtime, python_home=home,
        collector_port=15328, gateway_image=GATEWAY)
    helper.prepare_source_snapshot_mountpoints(copied)
    # Host-only identity resolver source: never mounted into the Task container.
    export(TASK, 'GenericAgent-main', dest / 'identity_source')
    ga = dest / 'identity_source/GenericAgent-main'
    shutil.rmtree(ga / 'monitor_agent_core')
    export(M1, 'GenericAgent-main/monitor_agent_core', dest / 'm1_source')
    shutil.copytree(dest / 'm1_source/GenericAgent-main/monitor_agent_core', ga / 'monitor_agent_core')
    (ga / 'temp').mkdir(exist_ok=True)
    (ga / 'mykey.py').write_text('\n'.join(k + ' = ' + repr(v) for k, v in profiles.items()), encoding='utf-8')
    for key in list(os.environ):
        if key.startswith('GA_'):
            del os.environ[key]
    env = dict(helper.DCEC_ENV)
    env.update(GA_EXPERIMENT_ID=BATCH, GA_CONDITION_ID='m1',
        GA_LLM_CONFIG_NAME='native_claude_cc_vibe_opus48', GA_MONITOR_SEMANTIC_CONTINUITY='1')
    helper.DCEC_ENV = env
    os.environ.update(env)
    os.environ.update(GA_HOST_ROOT=str(ga), CLAW_SWE_M3_ROOT=str(dest / 'claw_swe'),
        CLAW_SWE_M3_LOCKS=str(dest / 'claw_swe/locks.jsonl'))
    sys.path.insert(0, str(bench))
    from scripts import run_claw_swe_m3 as m3
    m3.REGISTRY = HERE / 'sphinx_registry.jsonl'
    # Use existing pinned dataset cache, not a dataset update or hidden source import.
    m3.PARQUET = ROOT / 'long_context_bench/output/m2_claw_swe/hf-cache/hub/datasets--princeton-nlp--SWE-bench_Verified/snapshots' / m3.DATASET_REVISION / 'data/test-00000-of-00001.parquet'
    m3.COLLECTOR_PORT = 15328
    m3.COLLECTOR_NAME = 'm1-core4-sphinx-otel'
    identity_spec = importlib.util.spec_from_file_location('core4_m2_identity', m3.M2_SCRIPT)
    identity = importlib.util.module_from_spec(identity_spec)
    identity_spec.loader.exec_module(identity)
    os.environ['GA_METHOD_EXPECTED_SOURCE_SHA256'] = identity._ga_source_hash()
    ready = m3.scan('all', False, False, [INSTANCE])
    if len(ready) != 1 or ready[0]['status'] != 'ready':
        raise RuntimeError('Sphinx immutable source/task readiness mismatch')
    locks = m3.load_locks()
    if locks[INSTANCE]['image']['image_id'] != IMAGE:
        raise RuntimeError('Sphinx locked image mismatch')
    token = hashlib.sha256(args.run_id.encode()).hexdigest()[:12]
    volume, gateway = 'core4-' + token, 'core4-gateway-' + token
    helper.install_isolated_adapter(m3, copied, volume)
    configured = m3.configure_m2_for_lock
    def configure(lock):
        module = configured(lock)
        install_archive_and_environment(module, args.output_root, args.run_id,
            dest / 'isolated_bundle/virtual_monitor_profiles.json')
        return module
    m3.configure_m2_for_lock = configure
    gateway_root = dest / 'isolated_bundle/gateway'
    result = dict(batch_id=BATCH, run_id=args.run_id, supervisor_commit=M1, task_commit=TASK,
        policy_enabled=False, model_profiles={k: {f: v for f, v in cfg.items()
            if f not in ('apikey', 'apibase')} for k, cfg in profiles.items()},
        environment_note_sha256=sha((HERE / 'SPHINX_ENVIRONMENT.txt').read_bytes()),
        source_sha256=os.environ['GA_METHOD_EXPECTED_SOURCE_SHA256'], run_finished=False, evaluated=False)
    (dest / 'launch_identity.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    if prepare_only:
        module = configure(locks[INSTANCE])
        adapter = module.M2GenericAgentAdapter(args.run_id, identity.resolve_model_identity(0), 7200)
        (adapter.artifacts_root / INSTANCE).mkdir(parents=True, exist_ok=True)
        command = adapter.build_exec_command('synthetic-agent', 'synthetic-container', INSTANCE)
        mounts = adapter.container_run_args(INSTANCE)
        (dest / 'prepare_only_receipt.json').write_text(json.dumps(dict(
            source_identity=result, readiness=ready, command=command, mounts=mounts,
            container_started=False, real_provider_requests=0, virtual_credentials=True), indent=2), encoding='utf-8')
        return
    helper.docker('volume', 'create', volume)
    try:
        py = '/opt/m2-runtime/python/' + home + '/bin/python3.12'
        helper.docker('run', '-d', '--rm', '--name', gateway, '--network', 'bridge',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--read-only',
            '--add-host', 'host.docker.internal:host-gateway',
            '--mount', f'type=bind,src={runtime.resolve()},dst=/opt/m2-runtime,readonly',
            '--mount', f'type=bind,src={gateway_root.resolve()},dst=/gateway,readonly',
            '--mount', f'type=volume,src={volume},dst=/run/model-channel',
            GATEWAY, py, '/gateway/transport.py', 'gateway', '--config', '/gateway/config.json')
        for _ in range(60):
            probe = helper.docker('exec', gateway, py, '-c',
                "import socket;s=socket.socket(socket.AF_UNIX);s.connect('/run/model-channel/gateway.sock');s.close()", check=False)
            if probe.returncode == 0:
                break
            time.sleep(.5)
        else:
            raise RuntimeError('shared model gateway unavailable')
        m3.execute(INSTANCE, 'run', args.run_id, 7200, 0)
        result['run_finished'] = True
        # The original official harness remains unchanged; bound its outer process to 7200 s.
        # Existing m3 evaluation does not provide an outer subprocess timeout.
        original_run = m3.subprocess.run
        def bounded_run(command, *a, **kw):
            if isinstance(command, list) and 'swebench.harness.run_evaluation' in command:
                kw.setdefault('timeout', 7200)
            return original_run(command, *a, **kw)
        m3.subprocess.run = bounded_run
        try:
            m3.execute(INSTANCE, 'evaluate', args.run_id, 7200, 0)
            result['evaluated'] = True
        finally:
            m3.subprocess.run = original_run
    except BaseException as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        (dest / 'launch_result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        logs = helper.docker('logs', gateway, check=False, timeout=60)
        (dest / 'gateway_transport.log').write_text(logs.stdout + logs.stderr, encoding='utf-8')
        if not (Path(args.output_root) / 'archive_pause.json').exists():
            m3.stop_collector()
            helper.docker('rm', '-f', gateway, check=False, timeout=60)
            helper.docker('volume', 'rm', '-f', volume, check=False, timeout=60)
