"""Prepare one prompt-only comparison condition; never launch a task or call an API."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from clean_monitor_prepare_real_task_gate import build_manifest, ROOT

sys.path.insert(0, str(ROOT / 'GenericAgent-main'))
from monitor_agent_core.agent import monitor_system_prompt


def prepare(output, run_suffix, enabled=False):
    output = Path(output)
    if output.exists():
        raise FileExistsError('Refusing to overwrite an existing manifest')
    data = build_manifest('roadmapbench:fyn-2.2.0-roadmap', run_suffix, output)
    data['candidate'] = 'tool-feedback-guidance' if enabled else 'common-base'
    data['runs'][0]['environment'].update(
        GA_LLM_CONFIG_NAME='native_claude_cc_vibe_opus48',
        GA_MONITOR_GROUNDED_CONTEXT='0', GA_MONITOR_HANDOFF_VALIDATION='0',
        GA_MONITOR_ADVICE_REVISION='0', GA_MONITOR_FEEDBACK_FOCUS='0',
        GA_MONITOR_INQUIRY='0', GA_MONITOR_TOOL_FEEDBACK='1' if enabled else '0',
    )
    prompt = monitor_system_prompt(enabled)
    data['guidance_comparison'] = {
        'stable_system_prompt': prompt,
        'stable_system_prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
        'scope': 'One investigation paragraph; tools, scheduling and history unchanged.',
        'claim': 'Procedural prompt adaptation, not a faithful full CRITIC reproduction.',
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-suffix', required=True)
    parser.add_argument('--treatment', action='store_true')
    args = parser.parse_args()
    prepare(args.output, args.run_suffix, args.treatment)
    print(args.output)
