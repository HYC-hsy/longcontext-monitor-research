"""Prepare the approved wake-control validation; never execute on preparation."""
import json
from pathlib import Path
from clean_monitor_prepare_real_task_gate import build_manifest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'method_discovery/artifacts/wake_control_20260913'

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'fyne_r1_manifest.json'
    if path.exists():
        raise SystemExit('Manifest already exists; do not overwrite a run identity')
    manifest = build_manifest('roadmapbench:fyn-2.2.0-roadmap',
                              'wake-control-20260913-r1', path)
    manifest['candidate'] = 'wake-owned-stop-concurrent-followup'
    env = manifest['runs'][0]['environment']
    env['GA_LLM_CONFIG_NAME'] = 'native_claude_cc_vibe_opus48'
    env.update({
        'GA_PMA_ENABLED': '0', 'GA_MONITOR_GROUNDED_CONTEXT': '0',
        'GA_MONITOR_HANDOFF_VALIDATION': '0', 'GA_MONITOR_ADVICE_REVISION': '0',
        'GA_MONITOR_FEEDBACK_FOCUS': '0', 'GA_MONITOR_INQUIRY': '0',
        'GA_MONITOR_TOOL_FEEDBACK': '0', 'GA_MONITOR_ACTIVE_WORKING_CONTEXT': '1',
        'GA_MONITOR_LIVE_AWARENESS': '0', 'GA_MONITOR_DECISION_CONTEXT': '1',
    })
    manifest['comparison_limits'] = 'R2 historical diagnostic reference, not paired final-score evidence.'
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(path)
