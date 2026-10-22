"""Serial config frontend; preparation and real execution remain distinct."""
import argparse
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import importlib
import json
import os
from pathlib import Path

from .dataset_catalog import catalog, safe_task
from .methods import resolve

DRIVER = 'method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013'
PATH_KEYS = {'ga_source', 'runtime_root', 'worker_python', 'harbor_python',
             'bench_root', 'harbor_source_root', 'python_home'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def load_config(path):
    path = Path(path).resolve(strict=True)
    config = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(config, dict):
        raise ValueError('configuration must be an object')
    allowed = {'schema', 'dataset', 'method', 'slots', 'environment', 'runtime_policy',
               'native_context_policy', 'research_capture_policy', 'execution'}
    if set(config) - allowed or config.get('schema') != 'ga-experiment-plan-v1':
        raise ValueError('unknown configuration schema or keys')
    if config.get('execution', 'serial') != 'serial':
        raise ValueError('only serial execution is supported')
    from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.stateful_runtime_policy import policies
    policies(config)
    env = config.get('environment', {})
    if not isinstance(env, dict) or set(env) - {'paths', 'profiles', 'certifications', 'fake_only'}:
        raise ValueError('invalid environment section')
    if type(env.get('fake_only', False)) is not bool:
        raise ValueError('fake_only must be boolean')
    for section, keys in (('paths', PATH_KEYS), ('profiles', {'task_profile_file', 'pma_profile_file'})):
        mapping = env.get(section, {})
        if not isinstance(mapping, dict) or set(mapping) - keys:
            raise ValueError(f'invalid environment {section}')
    if not isinstance(env.get('certifications', {}), dict):
        raise ValueError('certifications must map method names to directories')
    for name in env.get('certifications', {}):
        resolve(name)
    if not isinstance(config.get('dataset'), dict):
        raise ValueError('dataset must be an object')
    for mapping in (config.get('dataset', {}), env.get('paths', {}),
                    env.get('profiles', {}), env.get('certifications', {})):
        for key in list(mapping):
            if key == 'commit' or key == 'python_home':
                continue
            value = mapping[key]
            if not isinstance(value, str) or not value:
                raise ValueError(f'empty or invalid path: {key}')
            mapping[key] = str((path.parent / value).resolve())
    return config


def build_plan(config):
    """Only Git public metadata and deterministic parsing, never profile execution."""
    if config.get('schema') != 'ga-experiment-plan-v1' or config.get('execution', 'serial') != 'serial':
        raise ValueError('expected ga-experiment-plan-v1 serial configuration')
    slots = config.get('slots')
    if not isinstance(slots, list) or not slots:
        raise ValueError('nonempty slots required')
    normalized = []
    seen = set()
    for row in slots:
        if not isinstance(row, dict) or set(row) - {'task', 'method', 'occurrence'}:
            raise ValueError('invalid slot fields')
        task = safe_task(row.get('task'))
        method = resolve(row.get('method', config.get('method')))
        occurrence = row.get('occurrence', 1)
        if type(occurrence) is not int or occurrence < 1:
            raise ValueError('occurrence must be a positive integer')
        identity = (task, method.name, occurrence)
        if identity in seen:
            raise ValueError('duplicate slot identity')
        seen.add(identity)
        if 'runtime_policy' in config and not method.supports_runtime_policy:
            raise ValueError(f'explicit runtime policy unsupported by adapter {method.name}')
        if any(key in config for key in ('native_context_policy', 'research_capture_policy')) and method.research_candidate != 'pma_stateful_memory_v1':
            raise ValueError(f'stateful transport policy unsupported by adapter {method.name}')
        normalized.append({'task': task, 'method': method.name, 'occurrence': occurrence,
                           'adapter': asdict(method)})
    public = catalog(config['dataset'], [row['task'] for row in normalized])
    by_task = {row['task']: row for row in public['tasks']}
    for row in normalized:
        if row['adapter']['supports_runtime_policy']:
            from .runtime_policy import resolve_policy
            asset = by_task[row['task']]
            row['requested_runtime_policy'] = config.get('runtime_policy', {})
            row['effective_runtime_policy'] = resolve_policy(row['requested_runtime_policy'], {
                'native_agent_seconds': asset['agent_timeout_sec'],
                'native_verifier_seconds': asset['verifier_timeout_sec']},
                {'task_turns_max': row['adapter']['task_turns_max']})
    body = {'schema': 'ga-experiment-resolved-v1', 'config': config,
            'catalog': public, 'slots': normalized, 'execution_authorized': False}
    return {**body, 'plan_sha256': digest(body)}


def _directory(order, row):
    # Method names are not paths; registration need not enforce filesystem names.
    return f'{order:02d}-{row["task"]}-r{row["occurrence"]}'


@contextmanager
def method_environment(method):
    overrides = method.runtime_environment(os.environ)
    previous = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _backend():
    return importlib.import_module(DRIVER + '.single_run')


def execute(plan, output, mode, backend=None):
    from importlib import import_module
    controller = import_module(DRIVER + '.run_selection').execute_serial
    config = plan['config']
    env = config.get('environment', {})
    profiles = env.get('profiles', {})
    if set(profiles) != {'task_profile_file', 'pma_profile_file'}:
        raise ValueError('legacy drivers require Task and PMA profile paths')
    paths = env.get('paths', {})
    if mode == 'run' and not PATH_KEYS - {'python_home'} <= paths.keys():
        raise ValueError('run requires all GA/Harbor/worker paths')
    # Existing drivers are fixed to this benchmark commit. Catalog remains general.
    commit = import_module(DRIVER + '.export_official_evaluator').COMMIT
    if config['dataset']['commit'] != commit:
        raise ValueError('legacy execution adapter only supports its pinned dataset commit')
    root = Path(output).resolve()
    if mode == 'run':
        saved = json.loads((root / 'experiment_plan.json').read_text(encoding='utf-8'))
        if saved != plan:
            raise ValueError('configuration/adapter/catalog changed since preparation')
        prep = json.loads((root / 'selection_preparation.json').read_text(encoding='utf-8'))
        if prep['remaining_not_started'] or any(r['status'] != 'prepared_not_authorized' for r in prep['slots']):
            raise ValueError('selection preparation did not complete')
    backend = backend or _backend()

    def prepare_call(directory, row):
        snapshot = root / 'experiment_plan.json'
        if not snapshot.exists():
            write_new(snapshot, plan)
        method = resolve(row['method'])
        args = dict(output=str(directory), task=row['task'], occurrence=row['occurrence'],
                    official_source_git=config['dataset']['source_git'], **profiles,
                    **method.prepare_fields(), fake_only=env.get('fake_only', False),
                    certification_dir=env.get('certifications', {}).get(method.name),
                    candidate_profile_fixture=False, synthetic_pos_fixture=False)
        if 'requested_runtime_policy' in row:
            args['runtime_policy'] = row['requested_runtime_policy']
        for key in ('native_context_policy', 'research_capture_policy'):
            if key in config:
                args[key] = config[key]
        outcome = backend.prepare(argparse.Namespace(**args))
        single = json.loads((directory / 'plan.json').read_text())
        actual_candidate = single.get('research_candidate', single.get('method', 'U'))
        if single.get('condition') != method.condition or actual_candidate != method.research_candidate:
            raise ValueError('driver prepared a different method identity')
        expected_response = 'complete-response-v1' if method.task_complete_response else 'disabled'
        if single.get('task_complete_response_policy', 'disabled') != expected_response:
            raise ValueError('driver prepared a different Task response protocol')
        manifest = json.loads((directory / 'manifest.json').read_text())
        if 'effective_runtime_policy' in row:
            if (single.get('runtime_policy') != row['requested_runtime_policy'] or
                    manifest.get('config', {}).get('runtime_policy') != row['effective_runtime_policy']):
                raise ValueError('driver ignored or changed the requested runtime policy')
        if method.research_candidate == 'pma_stateful_memory_v1':
            from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.stateful_runtime_policy import policies
            expected_policies = policies(config)
            if any(single.get(key) != value or manifest.get('config', {}).get(key) != value
                   for key, value in expected_policies.items()):
                raise ValueError('driver ignored or changed stateful transport policies')
        binding = {'plan_sha256': plan['plan_sha256'], 'slot': row,
                   'manifest_sha256': hashlib.sha256((directory / 'manifest.json').read_bytes()).hexdigest(),
                   'single_plan_sha256': hashlib.sha256((directory / 'plan.json').read_bytes()).hexdigest()}
        write_new(directory / 'frontend_binding.json', binding)
        return outcome

    def run_call(directory, row, authorization):
        binding = json.loads((directory / 'frontend_binding.json').read_text())
        expected = {'plan_sha256': plan['plan_sha256'], 'slot': row,
                    'manifest_sha256': hashlib.sha256((directory / 'manifest.json').read_bytes()).hexdigest(),
                    'single_plan_sha256': hashlib.sha256((directory / 'plan.json').read_bytes()).hexdigest()}
        if binding != expected:
            raise ValueError('prepared slot method/protocol/manifest binding changed')
        stateful_replies = None
        if env.get('fake_only', False) and resolve(row['method']).research_candidate == 'pma_stateful_memory_v1':
            driver = importlib.import_module(DRIVER + '.single_run')
            fixture = Path(driver.__file__).resolve().with_name('stateful_fixture_replies.json')
            actual_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
            manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
            if manifest.get('stateful_fake_replies_sha256') != actual_hash:
                raise ValueError('stateful fixture replies identity mismatch')
            stateful_replies = str(fixture)
        args = dict(output=str(directory), authorization=str(authorization), **profiles,
                    **paths, official_source_git=config['dataset']['source_git'],
                    zero_model_fixture=env.get('fake_only', False), candidate_profile_fixture=False,
                    stateful_fake_replies=stateful_replies)
        args.setdefault('python_home', 'cpython-3.12.12-linux-x86_64-gnu')
        with method_environment(resolve(row['method'])):
            return backend.run(argparse.Namespace(**args))

    return controller(plan['slots'], root, mode, prepare_call, run_call, _directory)


def succeeded(results, expected, mode):
    if len(results) != expected:
        return False
    for row in results:
        if mode == 'prepare':
            if row['status'] != 'prepared_not_authorized':
                return False
        elif (row['status'] != 'attempted' or row['result'].get('stop_reason') or
              (row['result'].get('arm') or {}).get('disposition') != 'completed'):
            return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('catalog', 'plan', 'prepare', 'run'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == 'catalog':
            write_new(args.output, catalog(config['dataset']))
        else:
            plan = build_plan(config)
            if args.command == 'plan':
                write_new(args.output, plan)
            else:
                results = execute(plan, args.output, args.command)
                if not succeeded(results, len(plan['slots']), args.command):
                    return 1
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f'{type(exc).__name__}: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
