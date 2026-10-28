"""Candidate host chain and replay tests; all responses are scripted, network forbidden."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from pma_evidence_review import claim_split as cs
from pma_evidence_review.tests import test_live_gate as host
from pma_evidence_review.tests.test_claim_split import split, verification, batch
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.transport import CapturedTransport, ResponseProtocolError


class ClaimSplitLiveTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def cycle(self, verdicts=('supported', 'supported'), repairs=(), *, bank=None,
              target=None, bad_split=False, quote=None, side_effect=None):
        bank = bank if bank is not None else host.LatestEvidenceGapMemory()
        calls, contents = [], []
        repair_limit = int(bool(repairs))
        answers, repairs = iter(verdicts), iter(repairs)
        async def fake(**kw):
            calls.append((agent.transport_phase, kw))
            if agent.transport_phase == 'maintenance':
                name, args = host.write('First assertion and second assertion.', target)
                if quote is not None: args['evidence'] = [{'quote': quote}]
                return host.reply([(name, args)])
            if agent.transport_phase == 'selection': return host.reply(content='<no_intervention/>')
            if agent.transport_phase == 'citation_repair': return host.reply(content=json.dumps(next(repairs)))
            if kw['prompt'].startswith('CLOSED MATERIAL'):
                m = json.loads(kw['prompt'].split('\n', 1)[1]); contents.append(m)
                if bad_split: return host.reply(content='{"claims":[]}')
                value = split(m['original_operation']['content'], ['First assertion.', 'Second assertion.'])
                value['op_index'] = m['original_operation']['op_index']
            else:
                m = json.loads(kw['prompt'].split('\n', 1)[1].split('\nSUBMITTED EVIDENCE ONLY')[0])
                content = m['original_operation']['content']
                fragments = content.split(' and ')
                rows = [verification(c['index'], next(answers), fragments[c['index'] - 1])
                        for c in m['all_claims']]
                for row in rows:
                    row['explanation'] = 'The submitted quote shows file creation, not this assertion.'
                value = batch(rows)
                if side_effect: side_effect(bank)
            return host.reply(content=json.dumps(value))
        agent = host.CitationGateMemoryAgent(task='synthetic', memory=bank, llm=NS(call=fake),
                    review_strategy=cs.STRATEGY, repair_limit=repair_limit)
        agent.prepare_visible_context('UNQUOTED SECRET', [{'source_id': 'e1', 'role': 'tool_observation',
            'order': 1, 'field_path': 'result', 'text': host.TEXT, 'record_digest': host.sha256(host.TEXT),
            'record_digest_kind': 'event'}])
        result = asyncio.run(agent.process('UNQUOTED SECRET', 1))
        return agent, result, calls, contents

    def test_candidate_only_publish_after_all_claims(self):
        a, r, calls, _ = self.cycle()
        self.assertTrue(r.operations[0].success)
        self.assertEqual([phase for phase, _ in calls], ['maintenance'] + ['citation_review'] * 2 + ['selection'])
        attempt = a.last_citation_gate_report['operations'][0]['attempts'][0]
        self.assertEqual(cs.validate_attempt(attempt)['verdict'], 'supported')
        self.assertEqual(len(cs.audit_calls(attempt)), 2)
        self.assertEqual(len(attempt['claim_reviews']), 2)
        self.assertEqual(a.pending_receipt['operations'][0]['outcome'], 'committed')
        self.assertTrue(all('UNQUOTED SECRET' not in req['prompt'] for phase, req in calls if phase == 'citation_review'))

    def test_one_failed_claim_keeps_whole_old_revision(self):
        bank = host.LatestEvidenceGapMemory(); key = bank.save_knowledge('old')
        a, r, calls, _ = self.cycle(('supported', 'insufficient'), bank=bank, target=key)
        self.assertEqual(a.repair_limit, 0)
        self.assertNotIn('citation_repair', [phase for phase, _ in calls])
        self.assertEqual(a.last_citation_gate_report['operations'][0]['engineering_status'], 'ok')
        self.assertFalse(r.operations[0].success)
        self.assertEqual(bank.knowledge[0].content, 'old')
        receipt = a.pending_receipt['operations'][0]
        self.assertEqual(receipt['target_memory_id'], key)
        self.assertIn('Original text “second assertion.”', receipt['review_reason'])
        self.assertNotIn('claim 2', receipt['review_reason'])

    def test_author_repair_restarts_split_and_every_review_no_third_bypass(self):
        for last in ('supported', 'insufficient'):
            bank = host.LatestEvidenceGapMemory(); key = bank.save_knowledge('old')
            repair = {'decision': 'replace', 'content': 'First repaired and second repaired.',
                      'evidence': [{'quote': 'synthetic file created.'}]}
            a, r, calls, materials = self.cycle(('supported', 'insufficient', 'supported', last),
                        [repair], bank=bank, target=key)
            self.assertEqual([p for p, _ in calls], ['maintenance'] + ['citation_review'] * 2 +
                             ['citation_repair'] + ['citation_review'] * 2 + ['selection'])
            self.assertEqual(r.operations[0].success, last == 'supported')
            attempts = a.last_citation_gate_report['operations'][0]['attempts']
            self.assertEqual(len(attempts), 2)
            self.assertNotEqual(attempts[0]['candidate']['revision_id'], attempts[1]['candidate']['revision_id'])
            self.assertEqual([len(row['claim_reviews']) for row in attempts], [2, 2])
            self.assertNotEqual(materials[0]['submitted_evidence'], materials[1]['submitted_evidence'])
            for row in attempts: cs.validate_attempt(row)
            issue = json.loads(next(req['prompt'] for phase, req in calls if phase == 'citation_repair'))['review_issue']
            self.assertIn('Original text “second assertion.”', issue['explanation'])
            self.assertIn('shows file creation, not this assertion', issue['explanation'])
            self.assertNotIn('claim 2', issue['explanation'])
            self.assertEqual(a.pending_receipt['operations'][0]['outcome'],
                             'committed_after_repair' if last == 'supported' else 'not_committed')

    def test_bad_split_and_unbound_quote_never_publish_or_repair(self):
        repair = {'decision': 'withdraw'}
        a, r, calls, _ = self.cycle(repairs=[repair], bad_split=True)
        self.assertFalse(r.operations[0].success)
        self.assertNotIn('citation_repair', [p for p, _ in calls])
        self.assertIn('split_schema', a.pending_receipt['operations'][0]['review_reason'])
        a, r, calls, _ = self.cycle(quote='First assertion and second assertion.')
        self.assertFalse(r.operations[0].success)
        self.assertNotIn('citation_review', [p for p, _ in calls])

    def test_stale_generation_cannot_commit_after_claim_passes(self):
        a, r, _, _ = self.cycle(side_effect=lambda b: b.update_status('external mutation'))
        self.assertFalse(r.operations[0].success)
        self.assertFalse(a.memory.knowledge)

    def test_certificate_reparse_rejects_passflag_and_source_tampering(self):
        a, _, _, _ = self.cycle()
        attempt = a.last_citation_gate_report['operations'][0]['attempts'][0]
        for change in ('raw', 'flag', 'split_status', 'source', 'missing', 'reordered'):
            row = deepcopy(attempt)
            if change == 'raw': row['batch']['raw_response'] = json.dumps(batch([verification(verdict='insufficient')]))
            if change == 'flag': row['verdict'] = 'insufficient'
            if change == 'split_status': row['split']['engineering_status'] = 'protocol_error'
            if change == 'source': row['request']['closed_material']['submitted_evidence'][0]['submitted_quote'] += 'invented'
            if change == 'missing': row['claim_reviews'].pop()
            if change == 'reordered': row['claim_reviews'].reverse()
            with self.subTest(change=change), self.assertRaises(ValueError): cs.validate_attempt(row)

    def test_available_finish_reason_truncation_blocks_even_valid_json(self):
        async def fake(**kw):
            return NS(content=json.dumps(split('x')), tool_calls=[], finish_reason='length')
        transport = CapturedTransport(NS(call=fake), fake=True)
        with self.assertRaisesRegex(ResponseProtocolError, 'truncated_response'):
            asyncio.run(transport.send(cs.split_request({'original_operation': {'content': 'x'}}, 0)))
        self.assertEqual(transport.records[0]['finish_reason'], 'length')


class ActualTraceInputTests(unittest.TestCase):
    def setUp(self): install_guard(self)

    def test_real_inputs_preserved_with_scripted_not_real_split_reviews(self):
        path = Path(__file__).resolve().parents[1] / 'claim_split_delivery/TRACE_FIXTURES.json'
        fixtures = json.loads(path.read_text())['fixtures']
        for fixture in fixtures:
            m = fixture['material']; op = m['original_operation']
            texts = fixture['reference_expectations_not_model_output']['assertions_to_preserve']
            extracted = split(op['content'], texts); extracted['op_index'] = op['op_index']
            # These judgments test gate mechanics only, never asserted to be new model results.
            scripted = [verification(i, 'supported' if i == 2 else 'insufficient', op['content'])
                        for i in range(1, len(texts) + 1)]
            from pma_evidence_review.transport import FakeClient
            transport = CapturedTransport(FakeClient([json.dumps(extracted), json.dumps(batch(scripted))]), fake=True)
            result = asyncio.run(cs.assess(cs.split_request(m, op['op_index']), transport))
            self.assertEqual(result['verdict'], 'insufficient')
            self.assertEqual(len(result['claims']), len(texts))
            self.assertEqual(transport.calls, 2)
            for row in [result['batch']]:
                prompt = row['request']['prompt']
                self.assertNotIn('historical_baseline_response', prompt)
                self.assertNotIn('reference_expectations', prompt)
                self.assertEqual(row['request']['submitted_evidence_sha256'], cs.identity(m['submitted_evidence']))
            if fixture['fixture_id'] == 'sqlite_call_19':
                self.assertEqual([e['submitted_quote'] for e in m['submitted_evidence']],
                                 ['No working C compiler found. Tried cc and gcc.'])
            else:
                self.assertEqual([e['event_order'] for e in m['submitted_evidence']], [13, 13, 19])
                self.assertIn('later evidence does not contradict', cs.VERIFY_SYSTEM)

    def test_actual_sqlite_feedback_reaches_author_as_original_portion(self):
        from pma_evidence_review.gate_control import repair
        from pma_evidence_review.transport import FakeClient
        path = Path(__file__).resolve().parents[1] / 'claim_split_delivery/TRACE_FIXTURES.json'
        fixture = json.loads(path.read_text())['fixtures'][0]
        m = fixture['material']; content = m['original_operation']['content']
        texts = fixture['reference_expectations_not_model_output']['assertions_to_preserve']
        extracted = split(content, texts)
        fragments = ['"./configure --help" in /app/sqlite/sqlite',
                     'No working C compiler found. Tried cc and gcc.',
                     'This blocks the configure step needed for gcov instrumentation.',
                     'The environment lacks a C compiler installation', 'SQLite source being ready']
        rows = [verification(i, 'supported' if i == 2 else 'insufficient', fragments[i-1])
                for i in range(1, 6)]
        rows[3]['explanation'] = 'The quote establishes failure to find a working compiler, not absence of an installation.'
        transport = CapturedTransport(FakeClient([json.dumps(extracted), json.dumps(batch(rows)),
                                                 '{"decision":"withdraw"}']), fake=True)
        report = asyncio.run(cs.assess(cs.split_request(m, 0), transport))
        issue = {'explanation': report['explanation']}
        asyncio.run(repair(transport, 'frozen maintenance fixture', 'memory_save_procedural',
                          {'content': content}, issue, 0))
        sent = json.loads(transport.records[-1]['request']['prompt'])['review_issue']['explanation']
        self.assertIn('Original text “The environment lacks a C compiler installation”', sent)
        self.assertIn('not absence of an installation', sent)
        self.assertNotIn('claim 4', sent)
        self.assertNotIn('Original text “No working C compiler found.', sent)
