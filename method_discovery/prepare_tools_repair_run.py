"""Prepare one approved same-task repair comparison; never overwrite a run."""
import json
from pathlib import Path
from clean_monitor_prepare_real_task_gate import build_manifest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'method_discovery/artifacts/tools_repair_20260913/fyne_r1_manifest.json'
BASE = ROOT / 'method_discovery/artifacts/tools_t23_20260913/fyne_r1_manifest.json'

if __name__ == '__main__':
    if OUT.exists():
        raise SystemExit('Manifest already exists; do not reuse run identity')
    previous = json.loads(BASE.read_text(encoding='utf-8'))
    manifest = build_manifest('roadmapbench:fyn-2.2.0-roadmap', 'tools-repair-20260913-r1', OUT)
    fresh = manifest['runs'][0]['environment']
    manifest['runs'][0]['environment'] = {
        **previous['runs'][0]['environment'],
        'GA_METHOD_EXPECTED_SOURCE_SHA256': fresh['GA_METHOD_EXPECTED_SOURCE_SHA256'],
        'GA_EXPERIMENT_HARNESS_SHA256': fresh['GA_EXPERIMENT_HARNESS_SHA256'],
    }
    manifest['candidate'] = 'live-wait-clock-and-grounded-guidance'
    manifest['comparison_baseline'] = str(BASE.relative_to(ROOT))
    manifest['comparison_limits'] = 'Single discovery run; scheduling and guidance changed together.'
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'manifest': str(OUT), 'run_id': manifest['runs'][0]['run_id'],
                      'source_sha256': manifest['generic_agent_source_sha256']}))
