"""P2-only derived view of accepted GA steps; never an evidence source.

Only observation/content is a GA next_prompt (agent_loop -> ga._get_anchor_prompt).
Tool results and commands are opaque data, even when they contain the same tags.
"""
import copy
import hashlib
import json
import re


def digest(text):
    return hashlib.sha256(text.encode('utf-8', errors='surrogatepass')).hexdigest()


def project_steps(entries):
    checkpoint = earlier_context = None
    rows, audit = [], {'removed': [], 'retained_unknown': []}
    for entry in entries:
        row = {k: copy.deepcopy(entry[k]) for k in
               ('step', 'analysis', 'plan', 'commands', 'observation',
                '_source_event_id', '_evidence_identity') if k in entry}
        raw = entry.get('observation', '')
        path = f"step/{entry.get('step')}/observation/content"
        try:
            envelope = json.loads(raw)
            if (not isinstance(envelope, dict) or set(envelope) != {'content', 'tool_results'}
                    or not isinstance(envelope['content'], str)
                    or not isinstance(envelope['tool_results'], list)):
                raise ValueError('unknown envelope')
            text = envelope['content']
            # Anchored grammar of the host-owned field, NOT a global tag scrubber.
            match = re.match(r'(\n### \[WORKING MEMORY\]\n'
                             r'(<earlier_context>\n.*?\n</earlier_context>\n)?'
                             r'<history>\n.*?\n</history>)(\nCurrent turn: [0-9]+\n)'
                             r'(\n<key_info>.*?</key_info>)?', text, re.DOTALL)
            if not match:
                raise ValueError('unknown next_prompt')
            removed = match.group(1) + (match.group(4) or '')
            # Ambiguous nested delimiter text is not guessed away.
            for tag in ('history', 'earlier_context', 'key_info'):
                if text.count('<' + tag + '>') != text.count('</' + tag + '>') or text.count('<' + tag + '>') > 1:
                    raise ValueError('ambiguous next_prompt')
            audit['removed'].append({'path': path, 'sha256': digest(removed),
                                     'characters': len(removed)})
            if match.group(2):
                earlier_context = (len(rows), match.group(2))
            if match.group(4):
                checkpoint = (len(rows), match.group(4))
            envelope['content'] = match.group(3) + text[match.end():]
            row['observation'] = envelope
        except (ValueError, TypeError):
            audit['retained_unknown'].append({'path': path, 'sha256': digest(raw)})
        rows.append(row)
    if checkpoint is not None:
        index, text = checkpoint
        rows[index]['latest_framework_checkpoint_not_selectable'] = text
        audit['retained_checkpoint_sha256'] = digest(text)
    if earlier_context is not None:
        index, text = earlier_context
        rows[index]['latest_earlier_context_not_selectable'] = text
        audit['retained_earlier_context_sha256'] = digest(text)
    audit['input_sha256'] = digest(json.dumps(entries, ensure_ascii=True, sort_keys=True))
    return rows, audit


def render_selection(catalogue, status, steps, step_count, status_binding='',
                     memory_note='Memory is derived; source alignment is NOT semantic proof.'):
    return (f'## Step {step_count}\n\n## Selectable catalogue\n'
            + json.dumps(catalogue, ensure_ascii=False, sort_keys=True)
            + '\n' + memory_note + '\n'
            + '\n## Current internal status (not selectable)\n' + (status or '(no status)')
            + '\n' + status_binding
            + '\n\n## Recent visible steps (not selectable)\n'
            + json.dumps(steps, ensure_ascii=False, sort_keys=True)
            + '\n\nOnly TASK and the listed M aliases may be selected. Status and recent\n'
              'visible steps are judgment context only. Return one bare\n'
              '<intervene>TASK,M1</intervene> or <no_intervention/>.\n')
