"""Prepare same-task comparison manifests; never starts Docker or calls a model."""
import json
from pathlib import Path

from clean_monitor_prepare_real_task_gate import build_manifest, ROOT


OUT = ROOT / 'method_discovery/artifacts/root_decision_20260917'
BASE = ROOT / 'method_discovery/artifacts/pma_two_phase_20260913/fyne_r9_manifest.json'


def prepare():
    previous = json.loads(BASE.read_text(encoding='utf-8'))
    manifests = {}
    for name in ('decision', 'simple'):
        path = OUT / f'fyne_{name}_manifest.json'
        manifest = build_manifest('roadmapbench:fyn-2.2.0-roadmap',
                                  f'root-{name}-20260917-r1', path)
        env = manifest['runs'][0]['environment']
        identity = {key: env[key] for key in (
            'GA_METHOD_EXPECTED_SOURCE_SHA256', 'GA_EXPERIMENT_HARNESS_SHA256')}
        env.update(previous['runs'][0]['environment'])
        env.update(identity)
        env['GA_MONITOR_ROOT_DECISION_CONTRACT'] = '1' if name == 'decision' else '0'
        env['GA_MONITOR_ROOT_SIMPLE_CHECK'] = '1' if name == 'simple' else '0'
        manifest['candidate'] = 'root-' + name
        manifest['comparison_baseline'] = str(BASE.relative_to(ROOT))
        manifest['comparison_limits'] = (
            'Discovery only; R9 is historical, not paired replication. Same current '
            'source, models, task and maximum budget; prompt lengths differ. '
            'No new memory representation or model-call stage. Launch requires confirmation.')
        manifests[name] = manifest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    left = manifests['decision']['runs'][0]['environment']
    right = manifests['simple']['runs'][0]['environment']
    differences = {k for k in left.keys() | right.keys() if left.get(k) != right.get(k)}
    assert differences == {'GA_MONITOR_ROOT_DECISION_CONTRACT', 'GA_MONITOR_ROOT_SIMPLE_CHECK'}
    print(json.dumps({'status': 'prepared_not_executed', 'runs': 2,
                      'environment_differences': sorted(differences)}))
    return manifests


if __name__ == '__main__':
    prepare()
