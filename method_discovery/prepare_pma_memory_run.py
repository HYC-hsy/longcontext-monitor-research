"""Prepare the PMA maintenance candidate; never launch or reuse a run."""
import argparse
import json
from pathlib import Path
from clean_monitor_prepare_real_task_gate import build_manifest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'method_discovery/artifacts/tools_repair_20260913/fyne_r2_manifest.json'

def prepare(attempt=1):
    if attempt < 1:
        raise ValueError('attempt must be positive')
    output = ROOT / f'method_discovery/artifacts/pma_memory_20260913/fyne_r{attempt}_manifest.json'
    if output.exists():
        raise FileExistsError('Do not overwrite prior manifest or reuse run identity')
    previous = json.loads(BASE.read_text(encoding='utf-8'))
    manifest = build_manifest('roadmapbench:fyn-2.2.0-roadmap',
                              f'pma-memory-20260913-r{attempt}', output)
    fresh = manifest['runs'][0]['environment']
    manifest['runs'][0]['environment'] = {
        **previous['runs'][0]['environment'],
        'GA_METHOD_EXPECTED_SOURCE_SHA256': fresh['GA_METHOD_EXPECTED_SOURCE_SHA256'],
        'GA_EXPERIMENT_HARNESS_SHA256': fresh['GA_EXPERIMENT_HARNESS_SHA256'],
        'GA_MONITOR_PMA_MEMORY': '1',
    }
    manifest['candidate'] = 'author-pma-phase1-persistent-monitor-phase2'
    manifest['comparison_baseline'] = str(BASE.relative_to(ROOT))
    manifest['comparison_limits'] = ('Discovery comparison, not full PMA reproduction or causal proof. '
        'Adds one same-model maintenance call per wake and bank context; record added cost/latency.')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=int, default=1)
    print(prepare(parser.parse_args().attempt))
