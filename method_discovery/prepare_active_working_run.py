"""Prepare one isolated Fyne working-context candidate; never launch it."""
import argparse
import json
from pathlib import Path

from clean_monitor_prepare_real_task_gate import build_manifest


def prepare(output, suffix):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    data = build_manifest('roadmapbench:fyn-2.2.0-roadmap', suffix, output)
    data['candidate'] = 'active-working-context'
    data['runs'][0]['environment'].update(
        GA_LLM_CONFIG_NAME='native_claude_cc_vibe_opus48',
        GA_PMA_ENABLED='0', GA_MONITOR_GROUNDED_CONTEXT='0',
        GA_MONITOR_HANDOFF_VALIDATION='0', GA_MONITOR_ADVICE_REVISION='0',
        GA_MONITOR_FEEDBACK_FOCUS='0', GA_MONITOR_INQUIRY='0',
        GA_MONITOR_TOOL_FEEDBACK='0', GA_MONITOR_ACTIVE_WORKING_CONTEXT='1',
    )
    data['comparison_limits'] = (
        'Historical common-base Fyne is a diagnostic reference, not a same-environment '
        'paired control; a fresh isolated control needs separate launch approval.'
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--run-suffix', required=True)
    args = parser.parse_args()
    prepare(args.output, args.run_suffix)
    print('prepared_not_executed: ' + args.output)
