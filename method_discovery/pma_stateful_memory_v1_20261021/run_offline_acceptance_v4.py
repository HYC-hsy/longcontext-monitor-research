"""V4 immutable evidence capture; deny networking, never substitute token counts."""

import json
import runpy
import subprocess
import sys
import unittest

from .run_offline_acceptance_v2 import PACKAGE, REPO, git, sha


MODULE = 'method_discovery.pma_stateful_memory_v1_20261021'
DEST = PACKAGE / 'evidence' / 'final_contract_patch_v4' / 'run_02'
BASELINE = '9cddc758aaff9b982f8e2debd88bf280a2adc8e3'
V3_SOURCE = 'df2e0f8acc3f41be44d6bfd4a06341a264eee953'
LABELS = ('original_82', 'unittest_all', 'fake_scenarios', 'continuous_episode',
          'ga13_development_v4', 'contracts_without_tokenizer')
SCENARIOS = ('initial_task', 'clean_remind', 'clean_silent', 'issues_repair_clean',
             'audit_correction_exhausted', 'failed_then_replayed',
             'prefix_backlog', 'goal_epoch_stale')
LABELS += tuple('scenario_' + name for name in SCENARIOS)


def offline_child(label):
    def deny_network(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'urllib.Request'}:
            raise RuntimeError('offline_network_forbidden')
    sys.addaudithook(deny_network)
    # read_file is only reached on a missing/corrupt tokenizer cache. Existing
    # local tiktoken caches remain usable; missing data fails without a request.
    import tiktoken.load
    def missing_cache(path):
        raise RuntimeError('offline_tokenizer_cache_missing: ' + path)
    tiktoken.load.read_file = missing_cache
    if label.startswith('scenario_'):
        from .offline_fixture import scenario
        print(json.dumps(scenario(label[len('scenario_'):]), sort_keys=True))
        return
    if label == 'fake_scenarios':
        runpy.run_module(MODULE + '.offline_fixture', run_name='__main__')
        return
    loader = unittest.TestLoader()
    if label == 'unittest_all':
        suite = loader.discover(str(PACKAGE), pattern='test_*.py', top_level_dir=str(REPO))
    elif label == 'original_82':
        paths = git('ls-tree', '-r', '--name-only', BASELINE, '--',
                    str(PACKAGE.relative_to(REPO))).decode().splitlines()
        names = [MODULE + '.' + path.rsplit('/', 1)[1][:-3] for path in paths
                 if path.rsplit('/', 1)[1].startswith('test_') and path.endswith('.py')]
        suite = loader.loadTestsFromNames(names)
    elif label == 'contracts_without_tokenizer':
        names = [MODULE + '.test_final_contract_patch_v4.' + name for name in
            ('PromptContractV4Tests', 'InitializationV4Tests', 'CommitRetryV4Tests')]
        names.append(MODULE + '.test_ga13_dev_fixture_v4.GA13WitnessV4Tests')
        suite = loader.loadTestsFromNames(names)
    else:
        name = 'test_multiround_v2' if label == 'continuous_episode' else 'test_ga13_dev_fixture_v4'
        suite = loader.loadTestsFromName(MODULE + '.' + name)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'tests_run': result.testsRun, 'errors': len(result.errors),
        'failures': len(result.failures), 'skipped': len(result.skipped),
        'successful': result.wasSuccessful()}, sort_keys=True))
    if not result.wasSuccessful():
        raise SystemExit(1)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--child' and sys.argv[2] in LABELS:
        offline_child(sys.argv[2])
        return
    if DEST.exists():
        raise SystemExit('Refusing to replace existing V4 evidence')
    DEST.mkdir(parents=True)
    manifest = {'schema': 'stateful-memory-final-contract-patch-v4',
        'tested_commit': git('rev-parse', 'HEAD').decode().strip(),
        'baseline_archive': BASELINE, 'v3_runtime': V3_SOURCE,
        'transport': 'offline FakeProvider/FakeTask only; network denied in children',
        'real_model_calls': 0, 'real_tasks': 0, 'commands': {}, 'files': {},
        'source_identity': {}, 'source_worktree_diff': git('diff', '--exit-code').decode()}
    for label in LABELS:
        command = [sys.executable, '-B', '-m', MODULE + '.run_offline_acceptance_v4', '--child', label]
        result = subprocess.run(command, cwd=REPO, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240)
        manifest['commands'][label] = {'argv': command, 'exit_code': result.returncode}
        for channel, raw in (('stdout', result.stdout), ('stderr', result.stderr)):
            target = DEST / (label + '.' + channel + '.txt')
            target.write_bytes(raw)
            manifest['files'][target.name] = {'bytes': len(raw), 'sha256': sha(raw)}
    paths = git('ls-files', '--', str(PACKAGE.relative_to(REPO))).decode().splitlines()
    for path in paths:
        if not path.endswith('.py'):
            continue
        blob = git('show', 'HEAD:' + path)
        raw = (REPO / path).read_bytes()
        manifest['source_identity'][path] = {'git_blob_object': git('rev-parse', 'HEAD:' + path).decode().strip(),
            'git_blob_sha256': sha(blob), 'worktree_sha256': sha(raw)}
    (DEST / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False,
        sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'tested_commit': manifest['tested_commit'],
        'exit_codes': {key: value['exit_code'] for key, value in manifest['commands'].items()}}, sort_keys=True))
    if any(value['exit_code'] for value in manifest['commands'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
