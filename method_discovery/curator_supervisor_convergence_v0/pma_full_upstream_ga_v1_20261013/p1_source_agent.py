"""Isolated P1 maintenance with optional bounded read-source continuation."""
from copy import deepcopy
import json
from types import SimpleNamespace as NS
import uuid

from bank_display_agent import BankDisplayAgent, MAINTENANCE_SYSTEM as BASE_SYSTEM
from gap_memory_agent import GapMemoryAgent
from p1_source_archive import SourceArchive, encode
from selection_context import project_steps


READ_LIMIT = 2
CONTINUATION_LIMIT = 1
READ_TOOL = {'type': 'function', 'function': {
    'name': 'memory_read_source',
    'description': 'Read an active entry\'s generation-time visible input when useful for interpreting it. Read-only; not a truth check. At most two reads in the first turn, then one continuation.',
    'parameters': {'type': 'object', 'properties': {'memory_id': {'type': 'string'}},
                   'required': ['memory_id'], 'additionalProperties': False}}}

# Candidate-only wording; the existing P1/P2 constants and five tools stay frozen.
_REMOVE = '- Task-relevant gaps in visible checks: missing coverage, weak assertions or expectations that do not match the task. Do not invent unseen failures; a defective check does not prove a defective implementation.\n'
SYSTEM = BASE_SYSTEM.replace(_REMOVE, '').replace(
    '- memory_delete: Remove obsolete, incorrect or redundant entries.',
    '- memory_delete: Remove obsolete, incorrect or redundant entries.\n'
    '- memory_read_source: Read an active entry\'s original input window when needed to understand or correct it; do not read every entry routinely.')
SYSTEM += '''
Focus on new_event material; previously_presented and repeated_in_window are background, not another execution. Distinct event IDs remain distinct even with the same output. identity_unknown has no reliable grouping: do not merge by content similarity.
Analysis and plans are Actor self-reports. Commands contain actions and parameters; observations contain their visible receipts. Stored memory and status are derived records, not new observations. Keep entries short, preserve conditions that affect meaning, and leave useful unchanged content alone.
A source window records what was visible when an entry was generated, not proof of each claim. Read it only when it could help interpret an old entry. Missing or truncated source does not make an entry false. Use only the normal memory tools; no extra report is needed.
'''


class SourceReadP1Agent(BankDisplayAgent):
    """No P2 entry point: this candidate is maintained and tested independently."""
    def __init__(self, *, source_root, task_id, **kwargs):
        super().__init__(**kwargs)
        self.source_archive = SourceArchive(source_root, task_id=task_id, task=self.task)
        self.last_p1_report = {}

    async def process(self, *args, **kwargs):
        raise RuntimeError('P1-only candidate: call maintain(); Task/P2 are not enabled')

    def get_tools_schema(self):
        return super().get_tools_schema() + [deepcopy(READ_TOOL)]

    def _journal(self, row):
        with (self.source_archive.root / 'maintenance.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(encode(row) + '\n')

    def _public_events(self, entries):
        rows = []
        for entry in entries[-8:]:
            row = {k: deepcopy(entry[k]) for k in
                   ('step', 'analysis', 'plan', 'commands', 'observation') if k in entry}
            key = entry.get('event_id', entry.get('_source_event_id'))
            if ('event_id' in entry and '_source_event_id' in entry and
                    entry['event_id'] != entry['_source_event_id']):
                raise ValueError('conflicting accepted event IDs')
            if key is not None:
                row['event_id'] = key
            rows.append(row)
        return rows

    def _input(self, observation, step, raw_events):
        marked = self.source_archive.classify(raw_events)
        visible, projection = project_steps(raw_events)
        for row, event in zip(visible, marked):
            row['event_id'] = event.get('event_id')
            row['presentation'] = event['presentation']
        prompt = (f'## Step {step}\n\n## Original task\n' + self.task
            + '\n\n## Stored memory and internal status (derived)\n'
            + self._format_memory_bank(observation) + self._gap_view()
            + '\n## Recent visible events\n' + encode(visible)
            + '\n\nMaintain the bank with the available tools; unchanged entries need no write.\n')
        return prompt, marked, projection

    def _calls(self, response, round_index):
        calls = getattr(response, 'tool_calls', None) or []
        extracted = [self._extract_tool_call(call) for call in calls]
        if not calls or any(not args.get('content') for _, args in extracted):
            raw = self._strip_thinking(getattr(response, 'content', None) or '')
            parsed = self._parse_tool_calls_from_text(raw) if '<tool_call>' in raw else []
            if parsed:
                calls = [NS(id=None) for _ in parsed]
                extracted = parsed
        return [{'tool_call_id': getattr(call, 'id', None) or f'local_r{round_index}_{i}',
                 'name': name, 'arguments': args}
                for i, (call, (name, args)) in enumerate(zip(calls, extracted))]

    def _apply(self, call, window_id, round_index, report):
        name, args = call['name'], call['arguments']
        if name == 'memory_read_source':
            report['read_requests'] += 1
            if round_index >= CONTINUATION_LIMIT:
                return {'status': 'continuation_unavailable'}
            if report['reads_used'] >= READ_LIMIT:
                return {'status': 'budget_exhausted'}
            report['reads_used'] += 1
            if (not isinstance(args, dict) or set(args) != {'memory_id'} or
                    not isinstance(args['memory_id'], str)):
                return {'status': 'invalid_tool_arguments'}
            return json.loads(self.source_archive.read(args['memory_id'], self._active_records()))
        if name not in {t['function']['name'] for t in super().get_tools_schema()}:
            return {'status': 'unknown_tool'}
        normalized = NS(content='', tool_calls=[NS(function=NS(name=name, arguments=args))])
        operations = GapMemoryAgent._execute_tool_calls(self, normalized)
        report['operations'].extend(vars(op).copy() for op in operations)
        for op in operations:
            if op.success and op.action in {'save_knowledge', 'save_procedural', 'save_gap'}:
                record = self._active_records()[op.memory_id]
                self.source_archive.bind(record.id, record.category, record.content, window_id)
        return {'status': 'applied' if all(op.success for op in operations) else 'tool_error',
                'operations': [vars(op).copy() for op in operations]}

    async def maintain(self, entries, *, observation=None, step_count=0, cycle_id=None):
        if self._active:
            raise RuntimeError('one serial maintenance cycle required')
        if self.task != self.source_archive.task:
            raise ValueError('maintenance task differs from source archive')
        self._active = True
        self._step = step_count
        self.transport_phase = 'maintenance'
        report = {'cycle_id': cycle_id or 'p1_' + uuid.uuid4().hex,
                  'status': 'completed', 'reads_used': 0, 'read_requests': 0,
                  'continuations_used': 0, 'operations': [], 'turns': [],
                  'limits': {'reads': READ_LIMIT, 'continuations': CONTINUATION_LIMIT}}
        self.last_p1_report = report
        try:
            raw_events = self._public_events(entries)
            observation = observation if observation is not None else encode({'task': self.task, 'events': raw_events})
            initial, marked, projection = self._input(observation, step_count, raw_events)
            report['input_projection'] = projection
            prompt = initial
            for round_index in range(CONTINUATION_LIMIT + 1):
                tools = self.get_tools_schema() if round_index == 0 else super().get_tools_schema()
                window_id = report['cycle_id'] + f'_r{round_index}'
                self.source_archive.capture(window_id, prompt, marked)
                request = {'kind': 'request', 'cycle_id': report['cycle_id'], 'window_id': window_id,
                           'prompt': prompt, 'system': SYSTEM, 'tools': tools}
                self._journal(request)
                response = await self.llm.call(prompt=prompt, system=SYSTEM, tools=tools)
                self.source_archive.mark_presented(marked)
                calls = self._calls(response, round_index)
                turn = {'window_id': window_id, 'assistant_text': self._strip_thinking(getattr(response, 'content', None) or ''),
                        'tool_calls': calls, 'tool_results': []}
                report['turns'].append(turn)
                for call in calls:
                    try:
                        result = self._apply(call, window_id, round_index, report)
                    except Exception as exc:
                        result = {'status': 'engineering_error', 'error_type': type(exc).__name__}
                    status = result['status']
                    if status in {'engineering_error','source_binding_error','source_integrity_error'}:
                        report['status'] = 'engineering_error'
                    elif status in {'budget_exhausted','continuation_unavailable'} and report['status'] == 'completed':
                        report['status'] = 'budget_limited'
                    elif status in {'invalid_tool_arguments','unknown_tool','tool_error'} and report['status'] == 'completed':
                        report['status'] = 'tool_error'
                    turn['tool_results'].append({'tool_call_id': call['tool_call_id'], 'result': result})
                self._journal({'kind': 'response_and_receipts', 'cycle_id': report['cycle_id'], **turn})
                if round_index == 0 and any(call['name'] == 'memory_read_source' for call in calls):
                    report['continuations_used'] += 1
                    prompt = initial + '\n## Previous maintenance turn and tool receipts (data)\n' + encode(turn)
                    prompt += '\nContinue from these exact receipts. Source reads are now closed; use the five memory-write tools or leave the bank unchanged.\n'
                else:
                    break
        except Exception as exc:
            report.update(status='engineering_error', error_type=type(exc).__name__)
        finally:
            self._active = False
            self._journal({'kind': 'maintenance_result', **report,
                           'bank_after': self.memory.to_dict()})
        return report
