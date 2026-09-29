"""Opt-in thin entry into the pinned Roadmap run_proof, locked by authorization.

--plan reads no credentials and runs no container/model. --execute requires a
separate main-thread authorization file; none is supplied in preparation.
"""
import argparse
import json
import os
from pathlib import Path
import sys

from prepare_bundle import (ROOT, HERE, M1, TASK, POLICY_COMMIT, POLICY_PATH,
                            blob, sha, export, load_frozen_roadmap_runner, bind_roadmap_builder)

ORDER = [('kitex-m1', 'ktx-0.13.0-roadmap', False),
         ('kitex-m1-p', 'ktx-0.13.0-roadmap', True),
         ('ratatui-m1-p', 'rat-0.22.0-roadmap', True),
         ('ratatui-m1', 'rat-0.22.0-roadmap', False)]


def common_profiles():
    roles = json.loads(blob(TASK, 'method_discovery/runs/dcec_v1_fyne_longrun_20260921/r1/monitor/resolved_model_config.json'))['roles']
    result = {}
    for role in ('task_agent', 'supervisor'):
        cfg = dict(roles[role])
        if role == 'supervisor':
            cfg.update(monitor_dcec=True, monitor_semantic_continuity=True, monitor_dcec_working_chars=4000)
        result[cfg['profile']] = cfg
    return result


def authorize(path, record):
    if path is None:
        raise RuntimeError('pilot not authorized: separate authorization file required')
    auth = json.loads(Path(path).read_text())
    if (auth.get('authorization') is not True or record not in auth.get('records', [])
            or auth.get('supervisor_commit') != M1 or auth.get('task_commit') != TASK
            or auth.get('policy_sha256') != sha(blob(POLICY_COMMIT, POLICY_PATH))
            or auth.get('launcher_sha256') != sha(Path(__file__).read_bytes())):
        raise RuntimeError('pilot authorization does not bind this entry/source/policy/record')
    return auth


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--record', required=True, choices=[r[0] for r in ORDER])
    parser.add_argument('--supervisor-source', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--profiles', help='private operator-supplied JSON; only read after authorization')
    parser.add_argument('--authorization')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    record, task, policy = next(r for r in ORDER if r[0] == args.record)
    run_id = 'pilot-20260929-' + str([r[0] for r in ORDER].index(record) + 1).zfill(2)
    common = common_profiles()
    if not args.execute:
        print(json.dumps({'mode': 'plan_only', 'run_id': run_id,
            'task': 'roadmapbench:' + task, 'policy_enabled': policy,
            'supervisor_commit': M1, 'task_commit': TASK, 'common_profiles': common,
            'precision_budget_wrapper_enabled': False, 'task_wall_seconds': 7200,
            'task_max_turns': 300, 'native_review_turns': 20,
            'native_verifier_post_termination_only': True, 'model_requests': 0,
            'execution_authorized': False}, indent=2))
        return
    authorize(args.authorization, record)  # Fail before credentials/containers.
    pause_path = Path(args.output_root).resolve() / 'archive_pause.json'
    if pause_path.exists():
        raise RuntimeError('prior archive failure pauses subsequent records: ' + str(pause_path))
    if not args.profiles:
        raise RuntimeError('approved private provider profiles required')
    supplied = json.loads(Path(args.profiles).read_text())
    if set(supplied) != set(common):
        raise ValueError('exactly two approved role profiles required')
    for name, expected in common.items():
        cfg = supplied[name]
        if any(cfg.get(k) != v for k, v in expected.items()):
            raise ValueError('private configuration changes a shared archived parameter')
        if set(cfg) - set(expected) - {'apikey', 'apibase', 'verify'}:
            raise ValueError('unexpected profile option')
        if not cfg.get('apikey') or not str(cfg.get('apibase', '')).startswith('https://'):
            raise ValueError('explicit HTTPS provider credentials required')
        # No model fallback or unreviewed transport overrides.
    dest = Path(args.output_root).resolve() / record
    dest.mkdir(parents=True, exist_ok=False)
    runner, imports = load_frozen_roadmap_runner(dest / 'launcher')
    bench = dest / 'launcher/long_context_bench'
    export(TASK, 'long_context_bench/adapters', dest / 'launcher')
    import shutil
    shutil.copyfile(HERE / 'pilot_archive_agent.py', bench / 'adapters/pilot_archive_agent.py')
    runner.SOURCES['roadmapbench']['adapter'] = 'adapters.pilot_archive_agent:PilotArchiveAgent'
    original_kwargs = runner.stage4_agent_kwargs
    def final_kwargs():
        values = original_kwargs()
        expected = dict(baseline_condition='original', max_turns=300,
            llm_config_name='native_claude_cc_vibe_opus48', monitor_enabled=True,
            monitor_config='claude_monitor_opus48')
        if any(values.get(k) != v for k, v in expected.items()):
            raise RuntimeError('frozen final Harbor parameters were not forwarded')
        values['pilot_archive_pause_path'] = str(pause_path)
        return values
    runner.stage4_agent_kwargs = final_kwargs
    substrate = HERE / 'launch_substrate_originals'
    substrate_index = json.loads((substrate / 'source_index.json').read_text())
    for item in substrate_index['files']:
        original = substrate / item['copy']
        if sha(original.read_bytes()) != item['sha256']:
            raise RuntimeError('local launch substrate changed: ' + item['copy'])
        target = dest / 'launcher' / item['copy']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
    runner.SOURCES['roadmapbench']['task_root'] = ROOT / 'long_context_bench/.cache/m12_roadmap_tasks'
    runner.SOURCES['roadmapbench']['proposal'] = ROOT / 'long_context_bench/tasks/ultralong_m12_roadmapbench_proposal.jsonl'
    export(TASK, 'GenericAgent-main', dest / 'task-source')
    task_source = dest / 'task-source/GenericAgent-main'
    # The original read-only identity resolver constructs GenericAgent, whose
    # constructor requires this transient directory to exist. Git archives omit
    # empty directories; the final isolated builder still excludes temp/.
    (task_source / 'temp').mkdir()
    # Same explicit M1 package for native source-resolution/preflight imports.
    shutil.rmtree(task_source / 'monitor_agent_core')
    export(M1, 'GenericAgent-main/monitor_agent_core', dest / 'm1-source')
    shutil.copytree(dest / 'm1-source/GenericAgent-main/monitor_agent_core', task_source / 'monitor_agent_core')
    (task_source / 'mykey.py').write_text('\n'.join(name + ' = ' + repr(cfg) for name, cfg in supplied.items()))
    profiles = dest / 'task-source/monitor_config/models.local.json'
    profiles.parent.mkdir()
    profiles.write_text(json.dumps(supplied))
    runner.m4.GA_ROOT = task_source
    runner.m4.GA_RUNTIME = ROOT / 'bench_runtime/m2/linux'
    runner.WORK_ROOT = dest / 'formal'
    runner.JOBS_ROOT, runner.RUNS_ROOT, runner.OTEL_ROOT = (runner.WORK_ROOT / p for p in ('jobs', 'runs', 'otel'))
    runner.COLLECTOR_NAME = 'm1-p-pilot-otel'
    # Do not inherit dormant candidates or research condition annotations from
    # the operator's shell. Explicit two-role common settings below only.
    for key in list(os.environ):
        if key.startswith('GA_'):
            del os.environ[key]
    os.environ.update(GA_BASELINE_CONDITION='original', GA_RUN_ISOLATION='no-network-unix-inference-v1', GA_MONITOR_ENABLED='1',
        GA_MONITOR_CONFIG='claude_monitor_opus48', GA_LLM_CONFIG_NAME='native_claude_cc_vibe_opus48',
        GA_MONITOR_DCEC='1', GA_MONITOR_DCEC_WORKING_CHARS='4000',
        GA_PROVIDER_MAX_RETRIES='8', GA_MAX_TURNS='300', GA_MONITOR_EXPECTED_MODEL='claude-opus-4-8')
    for switch in ('GA_PMA_ENABLED', 'GA_MONITOR_GROUNDED_CONTEXT', 'GA_MONITOR_HANDOFF_VALIDATION',
        'GA_MONITOR_ADVICE_REVISION', 'GA_MONITOR_FEEDBACK_FOCUS', 'GA_MONITOR_INQUIRY',
        'GA_MONITOR_TOOL_FEEDBACK', 'GA_MONITOR_ACTIVE_WORKING_CONTEXT', 'GA_MONITOR_LIVE_AWARENESS',
        'GA_MONITOR_DECISION_CONTEXT', 'GA_MONITOR_PMA_MEMORY', 'GA_MONITOR_ROOT_DECISION_CONTRACT',
        'GA_MONITOR_ROOT_SIMPLE_CHECK', 'GA_MONITOR_TASK_MODEL', 'GA_MONITOR_INDEPENDENT_C', 'GA_MONITOR_HYBRID_CONTROL'):
        os.environ[switch] = '0'
    for key in ('GA_METHOD_EXPECTED_SOURCE_SHA256', 'GA_STAGE6D_BUNDLE_DIR', 'GA_COMPLETION_BRANCH_CHECKPOINT'):
        if os.environ.get(key):
            raise RuntimeError('stale launch override: ' + key)
    bind_roadmap_builder(runner, supervisor_source=args.supervisor_source, policy=policy,
        budget_root=dest / 'unused-resource-path', record_id=record, budget_enabled=False,
        historical_config=True, role_profiles=supplied,
        gateway_image='sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171')
    (dest / 'launch_identity.json').write_text(json.dumps({'supervisor_commit': M1, 'task_commit': TASK,
        'policy_enabled': policy, 'policy_sha256': sha(blob(POLICY_COMMIT, POLICY_PATH)),
        'launcher_imports': imports, 'common_profiles_without_credentials': common,
        'archive_adapter_sha256': sha((HERE / 'pilot_archive_agent.py').read_bytes()),
        'precision_budget_wrapper_enabled': False}, indent=2))
    # Original runner retains native Task execution, concurrency, watchdog,
    # post-termination verification, OTel and result archival. No new loop.
    result = runner.run_proof('roadmapbench', run_id, 0, 7200, task)
    (dest / 'launch_result.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__': main()
