"""Model envelope compatibility and actual cycle acceptance boundaries."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from .engine import CycleEngine
from .ga_fake_provider import FiniteGAFakeProvider
from .model_output import PROTOCOL, decode_model_object
from .source import ContractError, strict_loads
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf
from .test_engine import ScriptedProvider, event


class ModelEnvelopeTests(unittest.TestCase):
    def test_finite_host_fake_can_emit_the_same_fenced_protocol(self):
        fake = FiniteGAFakeProvider([{'role': 'selection', 'shape': 'silent',
                                     'envelope': 'fenced_json'}])
        binding = {'state_version': 1, 'task_version': 1,
                   'phase2_view_id': 'view'}
        answer = fake('selection', [{'role': 'system', 'content': 'x'},
            {'role': 'user', 'content': json.dumps({'binding': binding})}], 'call', 2048)
        self.assertEqual(decode_model_object(answer)['decision'], 'silent')
        self.assertEqual(len(fake.calls), 1)

    def test_accepted_envelopes_offsets_and_literal_payload(self):
        body = '{"text":"中文\\\" ` fence\\n  end"}'
        expected = strict_loads(body)
        cases = [body, ' \t\r\n' + body + '\n', '```\n' + body + '\n```',
                 '```json\r\n' + body + '\n```',
                 '\t```json\n' + body + '\r\n```\r\n']
        for raw in cases:
            with self.subTest(raw=raw[:20]):
                reports = []
                self.assertEqual(decode_model_object(raw, record=reports.append), expected)
                report = reports[0]
                self.assertEqual(report['protocol'], PROTOCOL)
                self.assertEqual(report['failure_layer'], None)
                start, end = report['payload_byte_start'], report['payload_byte_end']
                self.assertEqual(raw.encode()[start:end], body.encode())
                self.assertEqual(report['raw_utf8_sha256'], hashlib.sha256(raw.encode()).hexdigest())
                self.assertEqual(report['payload_utf8_sha256'], hashlib.sha256(body.encode()).hexdigest())
                self.assertEqual(report['envelope_kind'],
                    'fenced_json' if '```' in raw[:12] else 'raw_json')
        with self.assertRaises(ContractError):
            strict_loads('```json\n{}\n```')

    def test_ambiguous_or_invalid_envelopes_never_repaired(self):
        invalid = ['before\n```json\n{}\n```', '```json\n{}\n```\nafter',
                   '```JSON\n{}\n```', '``` json\n{}\n```', '```json{}\n```',
                   '```json\n{}\n``', '```json\n{}\n```\n```json\n{}\n```',
                   '{} {}', '```json\n{} {}\n```', '[]', 'null', '"x"',
                   '```json\n[]\n```', '{', '{"x":1,"x":2}',
                   '{"x":NaN}', '{"x":Infinity}', '{"x":"\ud800"}',
                   '```json\n{"x":1,"x":2}\n```']
        for raw in invalid:
            with self.subTest(raw=repr(raw)[:36]):
                reports = []
                with self.assertRaises(ContractError):
                    decode_model_object(raw, record=reports.append)
                self.assertEqual(len(reports), 1)
                self.assertIn(reports[0]['failure_layer'], {'envelope', 'json'})

    def _run(self, *, fenced=(), outcomes=(), remind=False, initial=False,
             malformed_first=False):
        with tempfile.TemporaryDirectory() as root:
            store = MemoryStore(Path(root) / 'memory.sqlite3')
            try:
                store.initialize(empty_snapshot(), leaf('task'))
                if not initial:
                    store.append_event(*event(1))
                base = ScriptedProvider(outcomes=outcomes,
                    create_requirement=True, remind=remind)
                roles = []
                def provider(role, messages, call_id, max_output):
                    roles.append(role)
                    if malformed_first and len(roles) == 1:
                        return '{"broken":true}'
                    raw = base(role, messages, call_id, max_output)
                    return '```json\n' + raw + '\n```' if role in fenced else raw
                result = CycleEngine(store, provider, task_text='task').run('envelope')
                rows = store.journal_rows(result['cycle_id'])
                return result, store.snapshot(), rows, roles
            finally:
                store.close()

    def test_initial_maintenance_audit_selection_fenced_no_extra_calls(self):
        raw = self._run(initial=True)
        fenced = self._run(initial=True, fenced={'maintenance', 'audit', 'selection'})
        for result, snapshot, rows, roles in (raw, fenced):
            self.assertEqual(result['status'], 'committed_selection_silent')
            self.assertEqual(result['logical_calls'], 3)
            self.assertEqual(roles, ['maintenance', 'audit', 'selection'])
            self.assertEqual(snapshot['state_version'], 1)
            self.assertNotIn('repair_credit_used', [row['phase'] for row in rows])
        self.assertEqual(raw[1], fenced[1])
        self.assertEqual([row['body']['envelope_kind'] for row in
            fenced[2] if row['phase'] == 'model_decode'], ['fenced_json'] * 3)

    def test_fenced_repair_and_exhausted_credit_are_distinct(self):
        result, snapshot, rows, roles = self._run(
            outcomes=['issues'], fenced={'maintenance', 'audit', 'candidate_repair',
                                         'selection'})
        self.assertEqual(result['status'], 'committed_selection_silent')
        self.assertEqual(roles, ['maintenance', 'audit', 'candidate_repair',
                                 'audit', 'selection'])
        self.assertEqual([row['phase'] for row in rows].count('repair_credit_used'), 1)
        result, snapshot, rows, roles = self._run(malformed_first=True,
            fenced={'maintenance', 'audit', 'selection'})
        self.assertEqual(result['status'], 'committed_selection_silent')
        self.assertEqual([row['phase'] for row in rows].count('repair_credit_used'), 1)
        self.assertEqual(roles, ['maintenance', 'maintenance', 'audit', 'selection'])
        self.assertEqual(snapshot['state_version'], 1)

    def test_fenced_audit_correction_uses_original_shared_credit(self):
        result, snapshot, rows, roles = self._run(outcomes=['malformed'],
            fenced={'maintenance', 'audit', 'audit_correction', 'selection'})
        self.assertEqual(result['status'], 'committed_selection_silent')
        self.assertEqual(roles, ['maintenance', 'audit', 'audit_correction',
                                 'selection'])
        self.assertEqual([row['phase'] for row in rows].count('repair_credit_used'), 1)
        self.assertEqual([row['body']['envelope_kind'] for row in rows
                          if row['phase'] == 'model_decode'], ['fenced_json'] * 4)

    def test_fenced_unusable_is_not_clean(self):
        result, snapshot, rows, roles = self._run(initial=True, outcomes=['unusable'],
            fenced={'maintenance', 'audit'})
        self.assertEqual(result['status'], 'init_failed')
        self.assertEqual(result['error_code'], 'model_unusable')
        self.assertEqual(snapshot['state_version'], 0)
        self.assertEqual(roles, ['maintenance', 'audit'])
        self.assertEqual([row['body']['outcome'] for row in rows
            if row['phase'] == 'audit_outcome'], ['unusable'])

    def test_fenced_schema_failure_still_rejects_and_selection_never_retries(self):
        with tempfile.TemporaryDirectory() as root:
            store = MemoryStore(Path(root) / 'memory.sqlite3')
            try:
                store.initialize(empty_snapshot(), leaf('task'))
                base = ScriptedProvider(create_requirement=True)
                roles = []
                def provider(role, messages, call_id, max_output):
                    roles.append(role)
                    if role == 'selection':
                        return '```json\n{"decision":"silent"}\n```'
                    return '```json\n' + base(role, messages, call_id, max_output) + '\n```'
                result = CycleEngine(store, provider, task_text='task').run('bad-select')
                self.assertEqual(result['status'], 'committed_selection_failed')
                self.assertEqual(result['logical_calls'], 3)
                self.assertEqual(roles, ['maintenance', 'audit', 'selection'])
                self.assertEqual(store.snapshot()['state_version'], 1)
                rows = store.journal_rows(result['cycle_id'])
                self.assertIn('schema', [row['body']['failure_layer'] for row in
                    rows if row['phase'] == 'model_validation_error'])
            finally:
                store.close()
