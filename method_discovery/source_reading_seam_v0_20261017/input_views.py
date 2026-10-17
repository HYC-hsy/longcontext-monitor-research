"""Strict, archived-input-only projections for the D1 Phase-2 source diagnostic.

The JSON decoder determines the command/output boundaries.  No JSON-looking
text inside a command, tool result, or task instruction is recursively decoded.
"""

from __future__ import annotations

import hashlib
import json
import re


PLACEHOLDER = 'Memory bank withheld in this diagnostic condition.'
CONTEXT = '## Context (Task Description + Recent Trajectory)\n'
RECENT = re.compile(r'\[Recent Trajectory \(last (\d+) steps\)\]\n\n')
STEP = re.compile(r'(?m)^\[Step (\d+)\]\n')
TASK_END = '\n\n## Your Task\n'
DECODER = json.JSONDecoder()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _json_at(text: str, start: int) -> tuple[object, str, int]:
    value, end = DECODER.raw_decode(text, start)
    return value, text[start:end], end


def project(original: str, view: str) -> tuple[str, dict]:
    """Return the exact F prompt or field-only EB/E projection and provenance."""
    if view not in ('F', 'EB', 'E'):
        raise ValueError('unknown input view')
    if original.count(CONTEXT) != 1 or original.count(TASK_END) != 1:
        raise ValueError('ambiguous archived context or task boundary')
    context_at = original.index(CONTEXT)
    task_at = original.index(TASK_END)
    if context_at >= task_at:
        raise ValueError('context occurs after task suffix')
    prefix = original[:context_at]
    context = original[context_at + len(CONTEXT):task_at]
    task_suffix = original[task_at:]
    if prefix.count('<memory_bank>') != 1 or prefix.count('</memory_bank>') != 1:
        raise ValueError('ambiguous memory bank')
    before, bank_tail = prefix.split('<memory_bank>', 1)
    bank, after = bank_tail.split('</memory_bank>', 1)
    if '<memory_bank>' in bank or '</memory_bank>' in after:
        raise ValueError('nested memory bank')
    recent = list(RECENT.finditer(context))
    if len(recent) != 1:
        raise ValueError('ambiguous recent trajectory header')
    task_text = context[:recent[0].start()]
    recent_header = context[recent[0].start():recent[0].end()]
    trajectory = context[recent[0].end():]
    matches = list(STEP.finditer(trajectory))
    if not matches or trajectory[:matches[0].start()] or len(matches) > int(recent[0].group(1)):
        raise ValueError('unexpected step count or unparsed trajectory prefix')
    projected_steps = []
    provenance = []
    for index, match in enumerate(matches):
        limit = matches[index + 1].start() if index + 1 < len(matches) else len(trajectory)
        block = trajectory[match.end():limit]
        if not block.startswith('Agent Analysis: '):
            raise ValueError('missing Agent Analysis')
        boundary = '\nCommands Executed: '
        if block.count(boundary) != 1:
            raise ValueError('ambiguous command boundary')
        analysis, remainder = block[len('Agent Analysis: '):].split(boundary, 1)
        command, command_raw, end = _json_at(remainder, 0)
        output_label = '\nTerminal Output: '
        if not isinstance(command, dict) or not remainder[end:].startswith(output_label):
            raise ValueError('invalid command object or output boundary')
        output_text = remainder[end + len(output_label):]
        output, output_raw, end = _json_at(output_text, 0)
        separator = output_text[end:]
        if separator not in ('', '\n\n'):
            raise ValueError('unparsed trailing step material')
        if (not isinstance(output, dict) or set(output) != {'content', 'tool_results'} or
                not isinstance(output['content'], str) or
                not isinstance(output['tool_results'], list)):
            raise ValueError('unexpected Terminal Output fields')
        results = output['tool_results']
        if not results or any(not isinstance(item, dict) or 'tool_use_id' not in item
                              for item in results):
            raise ValueError('missing independently identified tool result')
        raw_results = json.dumps(results, ensure_ascii=False)
        provenance.append({'step': int(match.group(1)), 'position': index,
                           'analysis': {'source_field': 'Agent Analysis',
                                        'sha256': digest(analysis), 'removed': view != 'F'},
                           'commands': {'source_field': 'Commands Executed',
                                        'sha256': digest(command_raw), 'preserved': True},
                           'output_content': {'source_field': 'Terminal Output.content',
                                              'sha256': digest(output['content']),
                                              'removed': view != 'F'},
                           'tool_results': {'source_field': 'Terminal Output.tool_results',
                                            'sha256_canonical': digest(raw_results),
                                            'count': len(results),
                                            'ids': [item['tool_use_id'] for item in results],
                                            'preserved': True},
                           'raw_output_sha256': digest(output_raw)})
        if view == 'F':
            projected_steps.append(trajectory[match.start():limit])
        else:
            output_new = json.dumps({'tool_results': results}, ensure_ascii=False)
            projected_steps.append(f'[Step {match.group(1)}]\n'
                                   f'Commands Executed: {command_raw}\n'
                                   f'Terminal Output: {output_new}{separator}')
    if view == 'E':
        prefix = before + '<memory_bank>\n' + PLACEHOLDER + '\n</memory_bank>' + after
    projected = (prefix + CONTEXT + task_text + recent_header + ''.join(projected_steps)
                 + task_suffix)
    if view == 'F' and projected != original:
        raise ValueError('F projection changed archived prompt')
    identity = {'view': view, 'original_prompt_sha256': digest(original),
                'projected_prompt_sha256': digest(projected),
                'bank_original_sha256': digest(bank),
                'bank_projected_sha256': digest(bank if view != 'E' else '\n' + PLACEHOLDER + '\n'),
                'task_description_sha256': digest(task_text),
                'recent_header_sha256': digest(recent_header),
                'task_suffix_sha256': digest(task_suffix),
                'step_count': len(matches), 'steps': provenance}
    return projected, identity
