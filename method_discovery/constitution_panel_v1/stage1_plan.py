"""Deterministic Stage 1 allocation; never imports a provider or sealed gold."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from preview_runner import assemble, load_inputs


PANEL = Path(__file__).resolve().parent
FIXTURE_COMMIT = '570356ced6ccc5d213c2bd49d7af15c51178039d'
PROFILE = 'claude_monitor_opus48'
EXPECTED_MODEL = 'claude-opus-4-8'
CASES = tuple(f'C{index:02d}' for index in range(1, 10))
CONDITIONS = ('current', 'constitution')
REPLICATES = (1, 2, 3)
FROZEN_PROMPTS = {
    'current': '7dc87726489093c55f164b8ed45c5e92f75856b2f4a6cac1dcea52e7707b7632',
    'constitution': 'e666f351233607db4f7c1b6bb716d99f45573381778cee3fd8aee6705e309e21',
}
SHELL_SHA = '61934d0b327cf5f47e6df50788e2736be956217ca402defc149c7af2e4472e13'
BLIND_MAP_COMMITMENT = '18e3fc8f2c92f9e36c7281cde9cbf62923d850381b6ae1c86f58523876608652'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def frozen_fixture_manifest(repo: Path, panel=PANEL):
    import subprocess
    relative = 'method_discovery/constitution_panel_v1/manifest.json'
    frozen = subprocess.check_output(['git', '-C', str(repo), 'show',
                                      f'{FIXTURE_COMMIT}:{relative}'])
    local = (panel / 'manifest.json').read_bytes()
    if local != frozen:
        raise ValueError('Panel manifest differs from frozen fixture commit')
    manifest = json.loads(frozen)
    preview_relative = 'method_discovery/constitution_panel_v1/preview_runner.py'
    preview_frozen = subprocess.check_output(['git', '-C', str(repo), 'show',
                                              f'{FIXTURE_COMMIT}:{preview_relative}'])
    if (panel / 'preview_runner.py').read_bytes() != preview_frozen:
        raise ValueError('Audited request assembly source differs from frozen fixture commit')
    if manifest.get('execution_authorized') is not False:
        raise ValueError('Historical fixture authorization changed')
    if manifest.get('frozen_cognitive_core_sha256') != FROZEN_PROMPTS:
        raise ValueError('Frozen cognitive core identities differ')
    if manifest['source_hashes'].get('prompts/panel_shell.txt') != SHELL_SHA:
        raise ValueError('Frozen common shell identity differs')
    if manifest['source_hashes'].get('prompts/constitution_cognitive_core.txt') != FROZEN_PROMPTS['constitution']:
        raise ValueError('Frozen Constitution source identity differs')
    if manifest['source_hashes'].get('prompts/current_cognitive_core.txt') != FROZEN_PROMPTS['current']:
        raise ValueError('Frozen current source identity differs')
    rows = manifest.get('cases') or []
    if tuple(row['case_id'] for row in rows) != CASES:
        raise ValueError('Frozen case allocation differs')
    for row in rows:
        relative = f"method_discovery/constitution_panel_v1/cases/{row['case_id']}/packet.json"
        source = subprocess.check_output(['git', '-C', str(repo), 'show',
                                          f'{FIXTURE_COMMIT}:{relative}'])
        local = (panel / 'cases' / row['case_id'] / 'packet.json').read_bytes()
        if sha(source) != row['packet_sha256'] or local != source:
            raise ValueError(f"Frozen packet identity differs: {row['case_id']}")
    for name, expected in (('panel_shell.txt', SHELL_SHA),
                           ('current_cognitive_core.txt', FROZEN_PROMPTS['current']),
                           ('constitution_cognitive_core.txt', FROZEN_PROMPTS['constitution'])):
        relative = f'method_discovery/constitution_panel_v1/prompts/{name}'
        source = subprocess.check_output(['git', '-C', str(repo), 'show',
                                          f'{FIXTURE_COMMIT}:{relative}'])
        if sha(source) != expected or (panel / 'prompts' / name).read_bytes() != source:
            raise ValueError(f'Frozen prompt identity differs: {name}')
    return manifest


def generate_plan(manifest):
    by_case = {row['case_id']: row for row in manifest['cases']}
    entries = []
    for case_index, case_id in enumerate(CASES):
        for replicate_index, replicate in enumerate(REPLICATES):
            first = CONDITIONS[(case_index + replicate_index) % 2]
            second = CONDITIONS[1 - (case_index + replicate_index) % 2]
            for condition in (first, second):
                identity = {'case_id': case_id, 'condition': condition,
                            'replicate': replicate, 'fixture_commit': FIXTURE_COMMIT}
                packet, shell, core = load_inputs(case_id, condition)
                request_hash = sha(canonical(assemble(packet, shell, core)))
                entries.append({
                    'ordinal': len(entries) + 1,
                    'trial_id': sha(canonical(identity))[:24],
                    'case_id': case_id, 'frame': by_case[case_id]['frame'],
                    'condition': condition, 'replicate': replicate,
                    'packet_sha256': by_case[case_id]['packet_sha256'],
                    'shell_sha256': SHELL_SHA,
                    'cognitive_core_sha256': FROZEN_PROMPTS[condition],
                    'request_sha256': request_hash,
                    'status': 'not_started',
                })
    return {
        'schema_version': 'constitution-panel-stage1-plan/1',
        'execution_authorized': False,
        'fixture_commit': FIXTURE_COMMIT,
        'profile': PROFILE, 'expected_model': EXPECTED_MODEL,
        'blind_map_commitment_sha256': BLIND_MAP_COMMITMENT,
        'order_rule': 'for C01..C09, replicate 1..3, first condition index '
                      '(case_index + replicate_index) % 2; second is opposite',
        'planned_logical_calls': len(entries), 'trials': entries,
    }


def write_plan(repo: Path, output: Path, panel=PANEL):
    manifest = frozen_fixture_manifest(repo, panel)
    plan = generate_plan(manifest)
    raw = json.dumps(plan, ensure_ascii=False, indent=2).encode('utf-8') + b'\n'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    return sha(raw)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Write deterministic zero-model Stage 1 plan')
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=PANEL / 'stage1' / 'PLAN.json')
    args = parser.parse_args()
    print(write_plan(args.repo.resolve(), args.output.resolve()))
