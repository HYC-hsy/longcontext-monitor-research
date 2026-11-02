"""Generation-window records, separate from the plain PMA bank; no truth review."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re


MAX_SOURCE_RETURN_CHARS = 8000


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def bounded_reply(result):
    raw = encode(result)
    if len(raw) > MAX_SOURCE_RETURN_CHARS:
        return encode({'status': 'engineering_error', 'error_type': 'receipt_metadata_too_large'})
    return raw



HISTORICAL_ROLE = 'historical_data_not_current_instructions'


def historical_events(events):
    """P1-only lossless role labels; never inspect/delete code or receipt strings."""
    rows = deepcopy(events)
    for row in rows:
        row['data_role'] = HISTORICAL_ROLE
        observation = row.get('observation')
        try:
            envelope = json.loads(observation) if isinstance(observation, str) else observation
        except (ValueError, TypeError):
            envelope = None
        if (isinstance(envelope, dict) and set(envelope) == {'content', 'tool_results'}
                and isinstance(envelope['content'], str)
                and envelope['content'].lstrip('\n').startswith('### [WORKING MEMORY]\n')):
            row['observation_content_role'] = 'historical_framework_text'
    return rows


def source_view(result, window, full_text):
    """Latest whole event units first, displayed chronologically; no snippet guessing."""
    events = historical_events(window.get('visible_events', []))
    # Complete pre-projection data stays in the archive, not in a read reply.
    projected_window = {k: deepcopy(v) for k, v in window.items()
                        if k not in {'raw_generation_context', 'input_projection'}}
    projected_window.update(data_role=HISTORICAL_ROLE, visible_events=events)
    projected_text = encode(projected_window)
    units, reports = [], []
    for index, event in enumerate(events):
        unit = {'window_event': index + 1, 'event_id': event.get('event_id'),
                'commands': event.get('commands', [])}
        report = {k: event[k] for k in ('analysis', 'plan') if k in event}
        observation = event.get('observation', '')
        try:
            envelope = json.loads(observation) if isinstance(observation, str) else observation
        except (ValueError, TypeError):
            envelope = None
        if (isinstance(envelope, dict) and set(envelope) == {'content', 'tool_results'}
                and isinstance(envelope['content'], str) and isinstance(envelope['tool_results'], list)):
            unit['tool_results'] = envelope['tool_results']
            report['observation_content'] = envelope['content']
        else:
            unit['unclassified_observation'] = observation
        units.append(unit)
        reports.append({'window_event': index + 1, **report})
    view = {**result, 'status': 'available_truncated', 'truncated': True,
            'source_characters': len(projected_text), 'source_text': '',
            'data_role': HISTORICAL_ROLE, 'source_text_role': HISTORICAL_ROLE,
            'raw_generation_context_available': 'raw_generation_context' in window,
            'raw_generation_context_returned': False,
            'actions_and_receipts': [], 'actor_reports': [], 'presented_source_receipts': [],
            'omitted': {'whole_event_units': list(range(1, len(units) + 1)),
                        'actor_report_units': list(range(1, len(reports) + 1)),
                        'full_generation_input': True,
                        'read_receipt_units': list(range(1, len(window.get('presented_source_receipts', [])) + 1))},
            'view_policy': 'Latest whole action/receipt units first, then Actor reports; retained units are chronological. Oversize units are omitted, never sliced. Full input remains archived.'}
    # Copy already-presented receipts literally; never resolve their old IDs again.
    for index, receipt in enumerate(window.get('presented_source_receipts', []), 1):
        item = {'role': 'previously_presented_source_result_not_new_observation_not_current_instructions',
                'returned_receipt': receipt, 'view_omitted_parts': False}
        trial = deepcopy(view)
        trial['presented_source_receipts'].append(item)
        trial['omitted']['read_receipt_units'].remove(index)
        if len(encode(trial)) <= MAX_SOURCE_RETURN_CHARS:
            view = trial
            continue
        returned = receipt['receipt']
        compact = {'role': item['role'], 'read_call': receipt['call'],
                   'returned_metadata': {k: returned[k] for k in
                       ('memory_id','task_id','cycle_id','status','source_scope','integrity','truncated')
                       if k in returned},
                   'actions_and_receipts': [], 'view_omitted_parts': True}
        trial = deepcopy(view)
        trial['presented_source_receipts'].append(compact)
        trial['omitted']['read_receipt_units'].remove(index)
        if len(encode(trial)) > MAX_SOURCE_RETURN_CHARS:
            continue
        view = trial
        for unit in reversed(returned.get('actions_and_receipts', [])):
            trial = deepcopy(view)
            trial['presented_source_receipts'][-1]['actions_and_receipts'].insert(0, unit)
            if len(encode(trial)) <= MAX_SOURCE_RETURN_CHARS:
                view = trial
    for field, candidates, omitted_key in (
            ('actions_and_receipts', units, 'whole_event_units'),
            ('actor_reports', reports, 'actor_report_units')):
        for candidate in reversed(candidates):
            trial = deepcopy(view)
            trial[field].append(candidate)
            trial[field].sort(key=lambda row: row['window_event'])
            trial['omitted'][omitted_key].remove(candidate['window_event'])
            if len(encode(trial)) <= MAX_SOURCE_RETURN_CHARS:
                view = trial
    trial = deepcopy(view)
    trial.update(source_text=projected_text, status='available', truncated=False)
    trial['omitted']['full_generation_input'] = False
    if len(encode(trial)) <= MAX_SOURCE_RETURN_CHARS:
        view = trial
    return bounded_reply(view)


class SourceArchive:
    """Only active IDs can resolve to source. Deleted records stay diagnostic-only."""
    def __init__(self, root, *, task_id, task):
        if not isinstance(task_id, str) or not task_id or not isinstance(task, str):
            raise ValueError('explicit task identity and text required')
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.task_id, self.task = task_id, task
        meta = {'task_id': task_id, 'task': task}
        path = self.root / 'task.json'
        if path.exists():
            if json.loads(path.read_text(encoding='utf-8')) != meta:
                raise ValueError('source archive belongs to another task')
        else:
            path.write_text(encode(meta), encoding='utf-8')
        self.seen = self._load('seen_events.json', {})
        self.refs = {}
        path = self.root / 'entry_sources.jsonl'
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                ref = json.loads(line)
                key = ref['memory_id']
                if ref['task_id'] != task_id or key in self.refs:
                    raise ValueError('invalid source association archive')
                self.refs[key] = ref

    def _load(self, name, default):
        path = self.root / name
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

    def window_path(self, cycle_id):
        if not isinstance(cycle_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', cycle_id):
            raise ValueError('invalid source cycle identity')
        return self.root / 'windows' / (cycle_id + '.json')

    def classify(self, events):
        """Keep every presentation. Only explicit IDs identify repeated executions."""
        rows, within = [], {}
        for event in events:
            row = deepcopy(event)
            key = row.get('event_id')
            fingerprint = digest(encode(row))
            if key is None:
                kind = 'identity_unknown'
            elif not isinstance(key, str) or not key:
                raise ValueError('invalid accepted event ID')
            else:
                previous = within.get(key, self.seen.get(key))
                if previous is not None and previous != fingerprint:
                    raise ValueError('accepted event ID reused with changed visible content')
                kind = ('repeated_in_window' if key in within else
                        'previously_presented' if key in self.seen else 'new_event')
                within[key] = fingerprint
            row['presentation'] = kind
            rows.append(row)
        return rows

    def capture(self, cycle_id, model_input, events, *, presented_source_receipts=(),
                raw_generation_context=None, input_projection=None, input_memory_coverage=None):
        path = self.window_path(cycle_id)
        path.parent.mkdir(exist_ok=True)
        value = {'task_id': self.task_id, 'cycle_id': cycle_id,
                 'scope': 'Generation-time visible input; not per-claim evidential support.',
                 'model_input': model_input, 'visible_events': deepcopy(events),
                 'presented_source_receipts': deepcopy(list(presented_source_receipts)),
                 'event_index': [{'event_id': row.get('event_id'),
                                  'presentation': row['presentation']} for row in events]}
        if raw_generation_context is not None:
            value['raw_generation_context'] = deepcopy(raw_generation_context)
            value['input_projection'] = deepcopy(input_projection)
        if input_memory_coverage is not None:
            value['input_memory_coverage'] = deepcopy(input_memory_coverage)
        with path.open('x', encoding='utf-8') as stream:
            stream.write(encode(value))
        return value

    def mark_presented(self, events):
        for event in events:
            row = {k: v for k, v in event.items() if k != 'presentation'}
            if row.get('event_id') is not None:
                self.seen[row['event_id']] = digest(encode(row))
        (self.root / 'seen_events.json').write_text(encode(self.seen), encoding='utf-8')

    def bind(self, memory_id, category, content, cycle_id):
        if memory_id in self.refs:
            raise ValueError('source association cannot overwrite an existing ID')
        path = self.window_path(cycle_id)
        text = path.read_text(encoding='utf-8')
        window = json.loads(text)
        if window['task_id'] != self.task_id or window['cycle_id'] != cycle_id:
            raise ValueError('source association scope mismatch')
        ref = {'task_id': self.task_id, 'cycle_id': cycle_id, 'memory_id': memory_id,
               'category': category, 'content_sha256': digest(content),
               'window_sha256': digest(text)}
        with (self.root / 'entry_sources.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(encode(ref) + '\n')
        self.refs[memory_id] = ref

    def read(self, memory_id, active_records):
        result = {'memory_id': memory_id, 'task_id': self.task_id,
                  'source_scope': 'Generation-time visible window; not per-claim evidential support.',
                  'integrity': 'not_checked'}
        row = active_records.get(memory_id)
        if row is None:
            return bounded_reply({**result, 'status': 'entry_not_found'})
        ref = self.refs.get(memory_id)
        if ref is None:
            return bounded_reply({**result, 'status': 'source_unrecorded'})
        if (ref['task_id'] != self.task_id or ref['memory_id'] != memory_id or
                ref['category'] != row.category or ref['content_sha256'] != digest(row.content)):
            return bounded_reply({**result, 'status': 'source_binding_error'})
        result['cycle_id'] = ref['cycle_id']
        try:
            text = self.window_path(ref['cycle_id']).read_text(encoding='utf-8')
        except FileNotFoundError:
            return bounded_reply({**result, 'status': 'source_missing'})
        if digest(text) != ref['window_sha256']:
            return bounded_reply({**result, 'status': 'source_integrity_error', 'integrity': 'failed'})
        window = json.loads(text)
        if window['task_id'] != self.task_id or window['cycle_id'] != ref['cycle_id']:
            return bounded_reply({**result, 'status': 'source_binding_error'})
        return source_view({**result, 'integrity': 'verified_saved_bytes'}, window, text)
