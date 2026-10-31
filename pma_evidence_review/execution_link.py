"""Domain-neutral projection of eligible quotes using host-validated source wrappers."""
from dataclasses import dataclass, asdict
from copy import deepcopy
from hashlib import sha256
import json
import re

RELATION_SCOPE = ('Execution records link selected command/output fragments from one verified '
                  'tool call; they add no omitted text and establish neither success nor '
                  'which script line produced an output.')
SCOPE_NOTE = ('Read host-linked execution fragments together. Distinguish conditions stated '
              'in the task or operation from inferences; an empty task excerpt adds no requirement. '
              'Evidence across different calls may jointly support a conclusion. Unlinked '
              'means no verified call relation, not automatic insufficiency or contradiction.')


class ProjectionError(ValueError):
    pass


def need(ok, code):
    if not ok:
        raise ProjectionError(code)


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def digest_text(value):
    return sha256(value.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class Context:
    frozen_sources: str
    frozen_inventory: str


def inventory_from_accepted_event(event):
    """Retain complete wrapper IDs and accepted-envelope identity, never event bodies."""
    public = {k: event[k] for k in ('event_id', 'sequence', 'kind',
              'initial_user_content', 'response', 'commands', 'observation',
              'step_status', 'actor_attempt') if k in event}
    digest = digest_text(json.dumps(public, sort_keys=True, ensure_ascii=False,
                              separators=(',', ':')))
    commands = event.get('commands', [])
    observation = event.get('observation', '{}')
    try:
        commands = [json.loads(c) if isinstance(c, str) else c for c in commands]
        observation = json.loads(observation) if isinstance(observation, str) else observation
        command_ids = [c.get('id') if isinstance(c, dict) else None for c in commands]
        result_ids = [r.get('tool_use_id') if isinstance(r, dict) else None
                      for r in observation.get('tool_results', [])]
    except (ValueError, TypeError, AttributeError):
        command_ids, result_ids = [None], [None]
    return {'event_id': event['event_id'], 'digest': digest,
            'digest_kind': 'accepted_public_envelope', 'order': event['sequence'],
            'commands': command_ids, 'outputs': result_ids}


def context_from_inventory(catalog, validate_catalog, accepted_inventory):
    """Pass the real catalog validator and this window's host-captured ID inventory."""
    validate_catalog(catalog)
    sources = {}
    def visit(snapshot):
        record = asdict(snapshot.record)
        sid = record['source_id']
        value = {'record': record, 'text': snapshot.blob.text}
        if sid in sources:
            need(sources[sid] == value, 'source_identity_changed')
            return
        sources[sid] = value
        if snapshot.parent_wrapper is not None:
            visit(snapshot.parent_wrapper)
    for visible in catalog.values():
        visit(visible.snapshot)
    inventory = {}
    for item in accepted_inventory.values():
        need(type(item) is dict and type(item.get('event_id')) is str and
             type(item.get('digest')) is str and item.get('digest_kind') == 'accepted_public_envelope'
             and type(item.get('order')) is int and type(item.get('commands')) is list
             and type(item.get('outputs')) is list, 'invalid_accepted_inventory')
        event_id = item['event_id']
        need(event_id not in inventory, 'duplicate_accepted_event')
        inventory[event_id] = {key: item[key] for key in ('digest', 'digest_kind', 'order',
                                                           'commands', 'outputs')}
    return Context(encoded(sources), encoded(inventory))


def context_from_catalog(catalog, validate_catalog, accepted_events):
    """Prototype-compatible path from accepted event objects, without new retrieval."""
    return context_from_inventory(catalog, validate_catalog,
        {key: inventory_from_accepted_event(event) for key, event in accepted_events.items()})


def _root(record, sources):
    seen = set()
    while record.get('parent_wrapper_source_id'):
        sid = record['parent_wrapper_source_id']
        if sid in seen or sid not in sources:
            return None
        seen.add(sid)
        record = sources[sid]['record']
    return record


def _side(record):
    path, role = record['field_path'], record['role']
    if role == 'tool_command' and re.fullmatch(r'commands/\d+', path):
        return 'command'
    if role == 'tool_observation' and re.fullmatch(r'observation/tool_results/\d+/content', path):
        return 'output'
    return None


def _key(record):
    call = record.get('tool_call_id')
    if (record['source_kind'] != 'public' or
            record.get('record_digest_kind') != 'accepted_public_envelope' or
            not isinstance(call, str) or not call):
        return None
    return (record['namespace'], record['event_id'], record['record_digest'], call)


def project(selected, context):
    """selected is the unchanged, upstream-admitted material.submitted_evidence.

    Context must be built from that cycle's validated catalog; never model input.
    This does not confer quote eligibility. Integrity failures are engineering
    errors. Missing IDs/wrappers and alternative-call ambiguity remain unlinked.
    """
    sources = json.loads(context.frozen_sources)
    inventory = json.loads(context.frozen_inventory)
    roots = {}
    for source in sources.values():
        root = _root(source['record'], sources)
        if root is not None:
            roots[root['source_id']] = root
    counts = {}
    for root in roots.values():
        key, side = _key(root), _side(root)
        if key is not None and side:
            counts.setdefault(key, {'command': set(), 'output': set()})[side].add(root['source_id'])
    quotes, resolved, bindings = [], [], []
    for i, row in enumerate(deepcopy(selected), 1):
        quote, origins = row['submitted_quote'], row['alternative_origins']
        need(type(quote) is str and quote and type(origins) is list and origins, 'selected_shape')
        choices, displays = [], []
        for origin in origins:
            sid = origin['source_id']
            need(sid in sources, 'missing_selected_snapshot')
            source = sources[sid]
            record, text = source['record'], source['text']
            need(record['source_id'] == sid and digest_text(text) == record['text_sha256'], 'source_identity')
            need(record['role'] == origin['role'] and record['field_path'] == origin['field_path']
                 and record['order'] == origin['event_order'], 'origin_identity')
            need(quote in text, 'quote_not_in_selected_source')
            root = _root(record, sources)
            key, side = _key(record), _side(root) if root else None
            valid = key is not None and root is not None and _key(root) == key and side
            valid = valid and all(len(counts.get(key, {}).get(s, ())) == 1 for s in ('command', 'output'))
            witness = inventory.get(record['event_id'], {})
            valid = valid and witness.get('digest_kind') == record['record_digest_kind']
            valid = valid and witness.get('digest') == record['record_digest'] and witness.get('order') == record['order']
            valid = valid and witness.get('commands', []).count(record.get('tool_call_id')) == 1 and witness.get('outputs', []).count(record.get('tool_call_id')) == 1
            choices.append((key, side) if valid else (None, None))
            displays.append({'role': origin['role'], 'field_path': origin['field_path'],
                             'event_order': origin['event_order']})
        unique = set(choices)
        resolved.append(next(iter(unique)) if len(unique) == 1 else (None, None))
        quotes.append({'label': f'E{i}', 'quote': quote, 'alternative_origins': displays})
        bindings.append({'label': f'E{i}', 'original_record': row, 'resolved': resolved[-1]})
    paired = {k for k, s in resolved if k is not None and s == 'command'} & {
        k for k, s in resolved if k is not None and s == 'output'}
    executions, aliases = [], {}
    for i, (key, side) in enumerate(resolved):
        if key is None:
            quotes[i]['link_status'] = 'unlinked_or_ambiguous'
            continue
        if key not in aliases:
            aliases[key] = len(executions)
            executions.append({'execution': f'X{len(executions)+1}',
                               'command_fragments': [], 'output_fragments': []})
        executions[aliases[key]][side + '_fragments'].append(f'E{i+1}')
        quotes[i]['link_status'] = ('same_call_pair' if key in paired else
                                    'verified_call_single_side')
    return Projection(encoded({'evidence': quotes, 'executions': executions,
                               'relation_scope': RELATION_SCOPE}),
                      encoded({'sources': sources, 'bindings': bindings,
                               'execution_keys': [list(k) for k in aliases]}))


@dataclass(frozen=True)
class Projection:
    model_json: str
    host_json: str

    def model_input(self):
        return json.loads(self.model_json)


def replace_evidence_view(existing_model_input, projection):
    view = deepcopy(existing_model_input)
    view['shared_submitted_evidence_B'] = projection.model_input()
    return view
