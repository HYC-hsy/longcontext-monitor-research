"""Zero-provider panel request assembler; there is intentionally no send path."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PANEL = Path(__file__).resolve().parent
PROMPTS = {'current': 'current_cognitive_core.txt',
           'constitution': 'constitution_cognitive_core.txt'}


def _tool(name, description, properties=None, required=None):
    return {'type': 'function', 'function': {'name': name, 'description': description,
        'parameters': {'type': 'object', 'properties': properties or {},
                       'required': required or [], 'additionalProperties': False}}}


def control_tools(frame):
    if frame not in {'local', 'root'}:
        raise ValueError('Unknown decision frame')
    tools = [
        _tool('wait', 'Do not send a corrective input now; leave the Task Agent to continue.'),
        _tool('intervene', 'Send one supervisory correction to the Task Agent.',
              {'message': {'type': 'string', 'description': 'The correction to send.'}}, ['message']),
    ]
    if frame == 'root':
        tools.append(_tool('allow_complete', 'Approve the pending whole-task completion.'))
    return tools


def assemble(packet, shell, cognitive_core):
    if set(packet) != {'case_id', 'frame', 'public_task', 'public_observations', 'decision_prompt'}:
        raise ValueError('Unexpected packet field')
    if not shell.strip() or not cognitive_core.strip():
        raise ValueError('Both common shell and cognitive core must be non-empty')
    body = json.dumps(packet, ensure_ascii=False, separators=(',', ':'))
    return {'system': shell.rstrip() + '\n\n' + cognitive_core.strip(),
            'messages': [{'role': 'user', 'content': body}],
            'tools': control_tools(packet['frame'])}


def load_inputs(case_id, prompt_name, panel=PANEL):
    if prompt_name not in PROMPTS:
        raise ValueError('Prompt must be current or constitution')
    manifest = json.loads((panel / 'manifest.json').read_text(encoding='utf-8'))
    entries = [row for row in manifest['cases'] if row['case_id'] == case_id]
    if len(entries) != 1 or entries[0]['status'] != 'BUILT_FOR_MAIN_AUDIT':
        raise ValueError('Case is absent or unbuildable')
    paths = [panel / 'cases' / case_id / 'packet.json',
             panel / 'prompts' / 'panel_shell.txt', panel / 'prompts' / PROMPTS[prompt_name]]
    sealed = (panel / 'sealed').resolve()
    for path in paths:
        resolved = path.resolve(strict=True)
        if resolved == sealed or sealed in resolved.parents:
            raise ValueError('Sealed material cannot be a model input')
    packet_path, shell_path, core_path = paths
    if hashlib.sha256(packet_path.read_bytes()).hexdigest() != entries[0]['packet_sha256']:
        raise ValueError('Packet bytes differ from manifest identity')
    hashes = manifest['source_hashes']
    for path in (shell_path, core_path):
        relative = path.relative_to(panel).as_posix()
        if relative in hashes and hashlib.sha256(path.read_bytes()).hexdigest() != hashes[relative]:
            raise ValueError('Frozen prompt bytes differ from manifest identity')
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    if packet['case_id'] != case_id:
        raise ValueError('Packet identity differs from selection')
    shell, core = shell_path.read_text(encoding='utf-8'), core_path.read_text(encoding='utf-8')
    if core.strip() == 'PENDING_MAIN_THREAD_REVIEW':
        raise ValueError('Constitution cognitive core has not been frozen by the main thread')
    return packet, shell, core


def preview(case_id, prompt_name, output, panel=PANEL):
    packet, shell, core = load_inputs(case_id, prompt_name, panel)
    request = assemble(packet, shell, core)
    raw = (json.dumps(request, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    output = Path(output).resolve()
    sealed = (panel / 'sealed').resolve()
    if output == sealed or sealed in output.parents:
        raise ValueError('A preview cannot be written inside sealed material')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    checksum = hashlib.sha256(raw).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_bytes((checksum + '\n').encode('ascii'))
    return checksum


def main():
    parser = argparse.ArgumentParser(description='Offline-only panel assembly; no provider transport')
    parser.add_argument('--prompt', required=True, choices=tuple(PROMPTS))
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(preview(args.case, args.prompt, args.output))


if __name__ == '__main__':
    main()
