"""Unarmed six-input U/V1/D1 archived Phase-2 comparison; fake transport only.

This reuses the original recorded prompt, not historical memory or a new Task
process. Labels remain in the host manifest and never enter the model prompt.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from harbor.llms.base import LLMResponse
from memory_agent.memory.memory_agent import PHASE2_SYSTEM

from decision_reminder_agent import phase2_prompt, phase2_system
from episode import construct_upstream


HERE = Path(__file__).resolve().parent
PUBLIC = HERE / 'generic_single_run_20261015/real_12_r1_public_20261016'
CASES = (('07', 235), ('14', 85), ('14', 105), ('22', 7),
         ('07', 161), ('18', 6))
VARIANTS = ('U', 'V1', 'D1')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_case(arm: str, step: int) -> dict:
    path = PUBLIC / arm / 'pma_requests_public.json'
    raw = path.read_bytes()
    rows = json.loads(raw)
    index = 2 * step - 1
    if index >= len(rows):
        raise RuntimeError('archived PMA step missing')
    selected = rows[index]
    if (selected.get('phase') != 'context_decision' or
            selected.get('system') != PHASE2_SYSTEM or
            selected.get('tools') is not None or
            not selected.get('prompt', '').startswith(f'## Step {step}\n')):
        raise RuntimeError('archived original Phase 2 identity mismatch')
    return {'source_path': path.relative_to(HERE).as_posix(),
            'source_file_sha256': sha(raw), 'prompt': selected['prompt'],
            'prompt_sha256': sha(selected['prompt'].encode('utf-8')),
            'system_sha256': sha(selected['system'].encode('utf-8')),
            'archive_index': index}


def requests() -> list[dict]:
    rows = []
    for arm, step in CASES:
        archive = read_case(arm, step)
        for variant in VARIANTS:
            prompt = (archive['prompt'] if variant == 'U' else
                      phase2_prompt(archive['prompt'], variant))
            system = PHASE2_SYSTEM if variant == 'U' else phase2_system(variant)
            rows.append({'arm': arm, 'pma_step': step, 'variant': variant,
                         'source_path': archive['source_path'],
                         'source_file_sha256': archive['source_file_sha256'],
                         'archive_index': archive['archive_index'],
                         'original_prompt_sha256': archive['prompt_sha256'],
                         'original_system_sha256': archive['system_sha256'],
                         'request_prompt_sha256': sha(prompt.encode('utf-8')),
                         'request_system_sha256': sha(system.encode('utf-8')),
                         'tools': None})
    return rows


def prepare(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 'pma-decision-phase2-screen-draft-v1',
                'execution_authorized': False,
                'scope': 'six_archived_Phase2_inputs_only_no_Task_no_Phase1',
                'planned_order': requests()}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2),
                                          encoding='utf-8')
    return {'requests': len(manifest['planned_order']),
            'execution_authorized': False,
            'manifest_sha256': sha((output / 'manifest.json').read_bytes())}


async def fake(manifest_path: Path, output: Path) -> dict:
    frozen = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (frozen.get('schema') != 'pma-decision-phase2-screen-draft-v1' or
            frozen.get('execution_authorized') is not False or
            frozen.get('planned_order') != requests()):
        raise RuntimeError('Phase 2 draft/source/variant identity changed')
    output.mkdir(parents=True, exist_ok=False)
    captures = []
    for number, row in enumerate(frozen['planned_order'], 1):
        source = read_case(row['arm'], row['pma_step'])
        variant = row['variant']
        expected_prompt = (source['prompt'] if variant == 'U' else
                           phase2_prompt(source['prompt'], variant))
        expected_system = PHASE2_SYSTEM if variant == 'U' else phase2_system(variant)
        slot = output / f'{number:02d}'
        slot.mkdir()
        agent = construct_upstream(slot / 'upstream',
                                   research_candidate=variant)
        sent = []

        async def fake_call(*, prompt, system, tools=None):
            sent.append({'prompt': prompt, 'system': system, 'tools': tools})
            return LLMResponse(content='<no_intervention/>')

        agent._memory_llm.call = fake_call
        response = await agent._memory_agent._call_llm_phase2(expected_prompt)
        parsed = agent._memory_agent._parse_phase2_response(response.content)
        if (sent != [{'prompt': expected_prompt, 'system': expected_system,
                      'tools': None}] or parsed is not None):
            raise RuntimeError('actual Phase 2 call/parser differs from draft')
        captures.append({'order': number, 'arm': row['arm'],
                         'pma_step': row['pma_step'], 'variant': variant,
                         'request': sent[0], 'raw_response': response.content,
                         'parsed_reminder': parsed})
    (output / 'actual_requests.json').write_text(json.dumps(captures, indent=2,
        ensure_ascii=False), encoding='utf-8')
    return {'fake_requests': len(captures), 'provider_requests': 0,
            'output_sha256': sha((output / 'actual_requests.json').read_bytes())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepared = sub.add_parser('prepare')
    prepared.add_argument('--output', type=Path, required=True)
    replay = sub.add_parser('fake')
    replay.add_argument('--manifest', type=Path, required=True)
    replay.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = (prepare(args.output) if args.command == 'prepare' else
              asyncio.run(fake(args.manifest, args.output)))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
