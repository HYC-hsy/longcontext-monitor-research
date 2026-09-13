"""Prepare only: same wake-control candidate, independent Claude monitor profile."""
import json
import argparse
from pathlib import Path
from clean_monitor_prepare_real_task_gate import build_manifest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'method_discovery/artifacts/claude_monitor_20260913'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--independent', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ('fyne_independent_r1_manifest.json' if args.independent else 'fyne_r1_manifest.json')
    if path.exists():
        raise SystemExit('Manifest exists; do not overwrite run identity')
    suffix = 'claude-independent-20260913-r1' if args.independent else 'claude-monitor-20260913-r1'
    manifest = build_manifest('roadmapbench:fyn-2.2.0-roadmap', suffix, path)
    manifest['candidate'] = 'wake-owned-stop-concurrent-followup-claude-monitor'
    env = manifest['runs'][0]['environment']
    env.update({
        'GA_LLM_CONFIG_NAME': 'native_claude_cc_vibe_opus48',
        'GA_MONITOR_CONFIG': 'claude_monitor_opus48',
        'GA_MONITOR_EXPECTED_MODEL': 'claude-opus-4-8',
        'GA_PMA_ENABLED': '0', 'GA_MONITOR_GROUNDED_CONTEXT': '0',
        'GA_MONITOR_HANDOFF_VALIDATION': '0', 'GA_MONITOR_ADVICE_REVISION': '0',
        'GA_MONITOR_FEEDBACK_FOCUS': '0', 'GA_MONITOR_INQUIRY': '0',
        'GA_MONITOR_TOOL_FEEDBACK': '0', 'GA_MONITOR_ACTIVE_WORKING_CONTEXT': '1',
        'GA_MONITOR_LIVE_AWARENESS': '0', 'GA_MONITOR_DECISION_CONTEXT': '1',
    })
    manifest['comparison_limits'] = (
        'Provider adaptation validation, not a controlled model-effect comparison; '
        'GPT wake-control run stopped before task. Older R2 is diagnostic context only.')
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(path)
