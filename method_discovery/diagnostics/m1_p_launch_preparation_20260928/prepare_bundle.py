"""Explicit experimental build_bundle adapter. Preparation only, never Docker/API.

Uses Git objects, not developer mykey.py or dirty worktree contents.
No runnable scientific authorization is supplied by this script.
"""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
M1 = '746a695adac4325d6440941d384d543d1364fef9'
TASK = '8b67de43cebf51d73b4327065713428cb049f161'
POLICY_COMMIT = 'c6e2b35820e472b48c93ee80b36d44d7a96582e5'
POLICY_PATH = 'method_discovery/diagnostics/rp_candidate_prototypes_20260927/P_POLICY.txt'
ADAPTER_PATH = 'method_discovery/diagnostics/m1_p_exact_acceptance_20260928/experimental_adapter.py'
LIMITS = dict(task_calls=300, monitor_calls=120, review_calls=20, panel_calls=1680,
    attempts_per_call=3, record_input=4000000, record_output=1000000,
    panel_input=16000000, panel_output=4000000, record_wall_seconds=9000,
    task_provider_seconds=7200, monitor_provider_seconds=1800,
    review_wall_seconds=600, panel_wall_seconds=43200)


def blob(commit, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', commit + ':' + path])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def export(commit, prefix, dest):
    data = subprocess.check_output(['git', '-C', str(ROOT), 'archive', '--format=zip', commit, prefix])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(dest)


def prepare(output, supervisor_source, policy=False, *, budget_root=None, record_id='engineering-fixture',
            runtime_source=None, python_home='UNVERIFIED_PYTHON_HOME', collector_port=15340):
    source = Path(supervisor_source).resolve(strict=True)
    if subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != M1:
        raise RuntimeError('explicit Supervisor source is not M1')
    if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=no']):
        raise RuntimeError('Supervisor tracked source is dirty')
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    with tempfile.TemporaryDirectory(prefix='pilot-prepare-') as temp:
        stage = Path(temp)
        export(TASK, 'GenericAgent-main', stage)
        task = stage / 'GenericAgent-main'
        # This is generated from the sanitized archive, never load real mykey.
        roles = json.loads(blob(TASK, 'method_discovery/runs/dcec_v1_fyne_longrun_20260921/r1/monitor/resolved_model_config.json'))['roles']
        configs = {}
        for role in ('task_agent', 'supervisor'):
            cfg = dict(roles[role])
            cfg.update(apikey='offline-virtual-key', apibase='https://offline.invalid',
                max_tokens=8192, max_retries=2)
            if role == 'supervisor':
                cfg.update(monitor_dcec=True, monitor_semantic_continuity=True,
                    monitor_dcec_working_chars=4000)
            configs[cfg['profile']] = cfg
        (task / 'mykey.py').write_text('\n'.join(k + ' = ' + repr(v) for k, v in configs.items()), encoding='utf-8')
        virtual = stage / 'monitor.json'
        virtual.write_text(json.dumps(configs), encoding='utf-8')
        utility_path = ROOT / 'long_context_bench/scripts/isolated_run_bundle.py'
        # Pin actual launch utility to reviewed Git bytes, not dirty current files.
        utility_file = stage / 'isolated_run_bundle.py'
        utility_file.write_bytes(blob(TASK, utility_path.relative_to(ROOT).as_posix()))
        spec = importlib.util.spec_from_file_location('pilot_isolated_bundle', utility_file)
        utility = importlib.util.module_from_spec(spec); spec.loader.exec_module(utility)
        # Utility's __file__ locates transport. Supply only the pinned transport.
        # Avoid writing outside our owned temp root: emulate original scripts layout.
        scripts = stage / 'bench' / 'scripts'; scripts.mkdir(parents=True)
        scripts_file = scripts / 'isolated_run_bundle.py'; scripts_file.write_bytes(utility_file.read_bytes())
        (stage / 'bench/adapters').mkdir()
        (stage / 'bench/adapters/isolated_transport.py').write_bytes(blob(TASK, 'long_context_bench/adapters/isolated_transport.py'))
        utility.__file__ = str(scripts_file)
        copied, compose = utility.build_bundle(output, task,
            Path(runtime_source).resolve(strict=True) if runtime_source else stage / 'runtime-not-mounted',
            python_home, 'native_claude_cc_vibe_opus48', 'claude_monitor_opus48',
            collector_port, monitor_profile_path=virtual)
        isolated_profiles = (copied / 'monitor_agent_core/models.local.json').read_bytes()
        shutil.rmtree(copied / 'monitor_agent_core')
        monitor_stage = stage / 'frozen'; monitor_stage.mkdir()
        export(M1, 'GenericAgent-main/monitor_agent_core', monitor_stage)
        pristine = monitor_stage / 'GenericAgent-main/monitor_agent_core'
        shutil.copytree(pristine, copied / 'monitor_agent_core')
        monitor_files = {p.relative_to(pristine).as_posix(): sha(p.read_bytes())
            for p in pristine.rglob('*') if p.is_file()}
        # Check provided source actually matches exported Git blobs (LF/CRLF only).
        for rel in monitor_files:
            runtime = (source / 'GenericAgent-main/monitor_agent_core' / rel).read_bytes()
            frozen = (pristine / rel).read_bytes()
            if runtime.replace(b'\r\n', b'\n') != frozen.replace(b'\r\n', b'\n'):
                raise RuntimeError('explicit M1 source bytes differ: ' + rel)
        policy_bytes = blob(POLICY_COMMIT, POLICY_PATH)
        if policy:
            (copied / 'pilot_policy.txt').write_bytes(policy_bytes)
        (copied / 'experimental_adapter.py').write_bytes(blob(TASK, ADAPTER_PATH))
        for name in ('pilot_bootstrap.py', 'resource_budget.py'):
            shutil.copyfile(HERE / name, copied / name)
        # Prelude is copied-bundle-only. Underlying Task/GA files remain pinned.
        for name, hook in [('ga_monitor_adapter.py', 'install'), ('agentmain.py', 'install_task')]:
            original = (copied / name).read_bytes()
            # Future import must stay first. Insert after it, if present.
            text = original.decode('utf-8')
            needle = 'from __future__ import annotations'
            prelude = '\nfrom pathlib import Path as _PilotPath\nfrom pilot_bootstrap import ' + hook + ' as _pilot_hook\n_pilot_hook(_PilotPath(__file__).resolve().parent)\n'
            if needle in text:
                text = text.replace(needle, needle + prelude, 1)
            else:
                text = prelude + text
            with (copied / name).open('w', encoding='utf-8', newline='\n') as stream:
                stream.write(text)
        binding = dict(schema='pilot-binding/1', preparation_only=True, execution_authorized=False,
            task_commit=TASK, monitor_commit=M1, monitor_files=monitor_files,
            monitor_git_blob_sha256={rel: sha(blob(M1, 'GenericAgent-main/monitor_agent_core/' + rel))
                for rel in monitor_files},
            policy_enabled=bool(policy), policy_sha256=sha(policy_bytes), budget_limits=LIMITS,
            configs=configs, adapter_sha256=sha((copied / 'experimental_adapter.py').read_bytes()),
            launcher_sha256=sha(blob(TASK, 'long_context_bench/scripts/run_ultralong_m12_proofs.py')),
            bundle_builder_sha256=sha(utility_file.read_bytes()),
            transport_sha256=sha(blob(TASK, 'long_context_bench/adapters/isolated_transport.py')),
            task_file_hashes={p.name: sha(p.read_bytes()) for p in task.glob('*.py') if not p.name.startswith('mykey')},
            experimental_preludes=['agentmain.py', 'ga_monitor_adapter.py'])
        binding['copied_task_file_hashes'] = {p.name: sha(p.read_bytes()) for p in copied.glob('*.py')}
        binding['experimental_source_hashes'] = {name: sha((HERE / name).read_bytes())
            for name in ('prepare_bundle.py', 'pilot_bootstrap.py', 'resource_budget.py', 'capture_worker.py')}
        (copied / 'pilot_binding.json').write_text(json.dumps(binding, indent=2), encoding='utf-8')
        # Client profile is separate from immutable monitor source identities.
        profile_path = output / 'virtual_monitor_profiles.json'
        profile_path.write_bytes(isolated_profiles)
        resources = Path(budget_root).resolve() if budget_root else output / 'resource-accounting'
        resources.mkdir(parents=True, exist_ok=True)
        topology = json.loads(compose.read_text())
        topology['services']['main'].setdefault('volumes', []).extend([
            f'{profile_path.as_posix()}:/pilot-config/models.json:ro',
            f'{resources.as_posix()}:/pilot-resource:rw'])
        topology['services']['main']['environment'] = {
            'MONITOR_CONFIG_FILE': '/pilot-config/models.json',
            'GA_MONITOR_ENABLED': '1', 'GA_MONITOR_CONFIG': 'claude_monitor_opus48',
            'GA_LLM_CONFIG_NAME': 'native_claude_cc_vibe_opus48',
            'GA_MONITOR_DCEC': '1', 'GA_MONITOR_DCEC_WORKING_CHARS': '4000',
            'GA_PROVIDER_MAX_RETRIES': '2', 'GA_MAX_TURNS': '300',
            'PILOT_BUDGET_PATH': '/pilot-resource/resource_audit.json',
            'PILOT_RECORD_ID': record_id}
        for switch in ('GA_PMA_ENABLED', 'GA_MONITOR_GROUNDED_CONTEXT',
            'GA_MONITOR_HANDOFF_VALIDATION', 'GA_MONITOR_ADVICE_REVISION', 'GA_MONITOR_FEEDBACK_FOCUS',
            'GA_MONITOR_INQUIRY', 'GA_MONITOR_TOOL_FEEDBACK', 'GA_MONITOR_ACTIVE_WORKING_CONTEXT',
            'GA_MONITOR_LIVE_AWARENESS', 'GA_MONITOR_DECISION_CONTEXT', 'GA_MONITOR_PMA_MEMORY',
            'GA_MONITOR_ROOT_DECISION_CONTRACT', 'GA_MONITOR_ROOT_SIMPLE_CHECK', 'GA_MONITOR_TASK_MODEL',
            'GA_MONITOR_INDEPENDENT_C', 'GA_MONITOR_HYBRID_CONTROL'):
            topology['services']['main']['environment'][switch] = '0'
        compose.write_text(json.dumps(topology, indent=2), encoding='utf-8')
        # Refresh real builder's deterministic snapshot hash after opt-in overlay.
        identity = json.loads((output / 'isolation_identity.json').read_text())
        identity.update(snapshot_sha256=utility.digest_tree(copied),
            supervisor_commit=M1, task_commit=TASK, post_bundle_opt_in=True,
            container_started=False, mount_verified=False, model_requests=0)
        (output / 'isolation_identity.json').write_text(json.dumps(identity, indent=2), encoding='utf-8')
        return copied, compose


def bind_roadmap_builder(runner, *, supervisor_source, policy, budget_root, record_id):
    """Explicit opt-in seam at the original run_proof -> build_bundle call.

    This preparation binding deliberately uses virtual credentials. It can
    construct launch artifacts but is NOT an authorized inference launcher.
    The original runner, Task loop and transport are not rewritten.
    """
    if getattr(runner, '_pilot_builder_bound', False):
        raise RuntimeError('pilot builder already bound')
    original = runner.build_bundle
    def configured(root, source, runtime, python_home, task_config, monitor_config,
                   collector_port, monitor_profile_path=None):
        if (task_config, monitor_config) != ('native_claude_cc_vibe_opus48', 'claude_monitor_opus48'):
            raise RuntimeError('unexpected role profiles at Roadmap bundle boundary')
        return prepare(root, supervisor_source, policy, budget_root=budget_root,
            record_id=record_id, runtime_source=runtime, python_home=python_home,
            collector_port=collector_port)
    runner.build_bundle = configured
    runner._pilot_builder_bound = True
    return original


def load_frozen_roadmap_runner(directory):
    """Fresh-process loading only. No preflight, main(), keys or Docker calls."""
    if any(k == 'scripts' or k.startswith('scripts.') for k in sys.modules):
        raise RuntimeError('Roadmap modules already loaded; use a fresh interpreter')
    export(TASK, 'long_context_bench/scripts', directory)
    bench = Path(directory) / 'long_context_bench'
    sys.path.insert(0, str(bench))
    import scripts.run_ultralong_m12_proofs as runner
    runner_files = {}
    for name, module in list(sys.modules.items()):
        if name.startswith('scripts.') and getattr(module, '__file__', None):
            p = Path(module.__file__).resolve()
            if not p.is_relative_to(bench):
                raise RuntimeError('mixed launch import: ' + name)
            rel = p.relative_to(Path(directory)).as_posix()
            original = blob(TASK, rel)
            if p.read_bytes().replace(b'\r\n', b'\n') != original.replace(b'\r\n', b'\n'):
                raise RuntimeError('launch import identity mismatch: ' + name)
            runner_files[name] = {'path': str(p), 'runtime_sha256': sha(p.read_bytes()),
                'git_blob_sha256': sha(original), 'lf_normalized_equal': True}
    return runner, runner_files


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--supervisor-source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--policy', action='store_true')
    parser.add_argument('--budget-root')
    parser.add_argument('--record-id', default='engineering-fixture')
    args = parser.parse_args()
    print(prepare(args.output, args.supervisor_source, args.policy,
        budget_root=args.budget_root, record_id=args.record_id))
