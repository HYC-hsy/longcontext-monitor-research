"""Offline request-preview skeleton. There is deliberately no provider path."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PANEL = Path(__file__).resolve().parent


def _tool(name, properties=None, required=None):
    return {'type': 'function', 'function': {'name': name,
        'parameters': {'type': 'object', 'properties': properties or {},
                       'required': required or [], 'additionalProperties': False}}}


def control_tools(frame):
    if frame not in {'local', 'root'}:
        raise ValueError('Unknown decision frame')
    tools = [_tool('wait'), _tool('intervene', {'message': {'type': 'string'}}, ['message'])]
    if frame == 'root':
        tools.append(_tool('allow_complete'))
    return tools


def assemble(packet, cognitive_guidance):
    if set(packet) != {'case_id', 'frame', 'public_task', 'prior_public_control',
                       'public_observations', 'decision_prompt'}:
        raise ValueError('Unexpected packet field')
    body = json.dumps(packet, ensure_ascii=False, separators=(',', ':'))
    return {'system': cognitive_guidance, 'messages': [{'role': 'user', 'content': body}],
            'tools': control_tools(packet['frame'])}


def load_inputs(case_id, prompt_name, panel=PANEL):
    if prompt_name not in {'current', 'constitution'}:
        raise ValueError('Prompt must be current or constitution')
    manifest = json.loads((panel / 'manifest.json').read_text(encoding='utf-8'))
    entries = [row for row in manifest['cases'] if row['case_id'] == case_id]
    if len(entries) != 1 or entries[0]['status'] != 'BUILT_FOR_MAIN_AUDIT':
        raise ValueError('Case is absent or UNBUILDABLE')
    packet_path = panel / 'cases' / case_id / 'packet.json'
    prompt_path = panel / 'prompts' / (prompt_name + ('_candidate' if prompt_name == 'constitution' else '') + '.txt')
    sealed = (panel / 'sealed').resolve()
    for path in (packet_path, prompt_path):
        resolved = path.resolve(strict=True)
        if resolved == sealed or sealed in resolved.parents:
            raise ValueError('Sealed material cannot be a model input')
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    prompt = prompt_path.read_text(encoding='utf-8')
    if prompt.strip() == 'PENDING_MAIN_THREAD_REVIEW':
        raise ValueError('Constitution candidate has not been frozen by the main thread')
    if packet['case_id'] != case_id:
        raise ValueError('Packet identity differs from manifest selection')
    if hashlib.sha256(packet_path.read_bytes()).hexdigest() != entries[0]['packet_sha256']:
        raise ValueError('Packet bytes differ from manifest identity')
    return packet, prompt


def preview(case_id, prompt_name, output, panel=PANEL):
    packet, prompt = load_inputs(case_id, prompt_name, panel)
    request = assemble(packet, prompt)
    raw = (json.dumps(request, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    output = Path(output).resolve()
    if output == (panel / 'sealed').resolve() or (panel / 'sealed').resolve() in output.parents:
        raise ValueError('A preview cannot be written inside sealed material')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    output.with_suffix(output.suffix + '.sha256').write_text(
        hashlib.sha256(raw).hexdigest() + '\n', encoding='ascii')
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Offline-only request assembly; no provider transport exists')
    parser.add_argument('--prompt', required=True, choices=('current', 'constitution'))
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(preview(args.case, args.prompt, args.output))


if __name__ == '__main__':
    main()
