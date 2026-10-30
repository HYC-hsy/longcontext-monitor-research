"""Focused scripted v4 protocol and live publication tests; no model effect claim."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from pma_evidence_review import claim_split_semantic as v4
from pma_evidence_review import claim_split_simple as v3
from pma_evidence_review.prompt_strategy import ONE_SENTENCE
from pma_evidence_review.tests.test_claim_split import material
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.transport import CapturedTransport, FakeClient
from pma_evidence_review.tests.test_live_gate import (
    CitationGateMemoryAgent, LatestEvidenceGapMemory, TEXT, reply, sha256)
from pma_evidence_review.split_v4_compare import plan


def judgment(verdict='supported'):
    return {'verdict': verdict, 'reason': 'Scripted evidence judgment.'}


def batch(verdict='supported'):
    return {'overall': judgment(verdict), 'results': [judgment(verdict)]}


class SemanticSplitTests(unittest.TestCase):
    def setUp(self): install_guard(self)

    def test_split_payload_has_no_evidence_and_batch_reuses_frozen_b(self):
        source = material('If enabled, the command ran and caused installation to succeed.')
        request = v4.split_request(source, 0)
        self.assertNotIn('submitted_evidence', request['prompt'])
        self.assertNotIn('A succeeded.', request['prompt'])
        self.assertIn('If enabled', request['prompt'])
        source['submitted_evidence'][0]['submitted_quote'] = 'mutated'
        transport = CapturedTransport(FakeClient([json.dumps(['If enabled, the command caused installation to succeed.']),
                                                  json.dumps(batch())]), fake=True)
        result = asyncio.run(v4.assess(request, transport))
        self.assertEqual(result['verdict'], 'supported')
        self.assertEqual(transport.calls, 2)
        self.assertIn('A succeeded.', transport.records[1]['request']['prompt'])
        self.assertNotIn('mutated', transport.records[1]['request']['prompt'])
        self.assertEqual(result['repair_feedback']['original_operation'], request['closed_material']['original_operation'])

    def test_partial_and_bad_cardinality_do_not_publish_semantic_success(self):
        request = v4.split_request(material(), 0)
        for answer, expected in [(batch('insufficient'), 'insufficient'),
                                 ({'overall': judgment(), 'results': []}, None)]:
            transport = CapturedTransport(FakeClient([json.dumps(['Whole original claim.']), json.dumps(answer)]), fake=True)
            result = asyncio.run(v4.assess(request, transport))
            self.assertEqual(result['verdict'], expected)
            self.assertEqual(result['engineering_status'], 'ok' if expected else 'parse_failure')
        self.assertEqual(v3.STRATEGY, 'claim-split-same-evidence-v3')

    def _cycle(self, calls, replies, *, bank=None, repair_limit=0, repairs=(),
               review_strategy=v4.STRATEGY):
        bank = bank if bank is not None else LatestEvidenceGapMemory()
        requests = []
        replies, repairs = iter(replies), iter(repairs)
        async def fake(**kwargs):
            requests.append((agent.transport_phase, kwargs))
            phase = agent.transport_phase
            if phase == 'maintenance': return reply(calls)
            if phase == 'selection': return reply(content='<no_intervention/>')
            if phase == 'citation_repair': return reply(content=json.dumps(next(repairs)))
            value = next(replies)
            return reply(content=json.dumps(value))
        agent = CitationGateMemoryAgent(task='synthetic', memory=bank, llm=NS(call=fake),
            review_strategy=review_strategy, repair_limit=repair_limit)
        agent.prepare_visible_context('UNQUOTED OBSERVATION', [{'source_id':'e1',
            'role':'tool_observation','order':1,'field_path':'result','text':TEXT,
            'record_digest':sha256(TEXT),'record_digest_kind':'event'}])
        result = asyncio.run(agent.process('UNQUOTED OBSERVATION', 1))
        return agent, result, requests

    def test_gap_delete_refusal_then_supported_commit_and_receipt(self):
        bank = LatestEvidenceGapMemory(); key = bank.save_gap('Tool not installed.')
        args = {'memory_id':key,'reason':'The tool is now installed.', 'evidence':[{'quote':TEXT}]}
        agent, result, requests = self._cycle([('memory_delete',args)], [['Tool is installed.'], batch('insufficient')], bank=bank)
        self.assertFalse(result.operations[0].success)
        self.assertEqual(bank.entries[0].id, key)
        self.assertEqual([phase for phase,_ in requests].count('citation_review'), 2)
        self.assertNotIn(TEXT, requests[1][1]['prompt'])
        self.assertIn('Tool not installed.', requests[1][1]['prompt'])
        self.assertEqual(agent.pending_receipt['operations'][0]['outcome'], 'not_committed')
        agent, result, requests = self._cycle([('memory_delete',args)], [['Tool is installed.'], batch()], bank=bank)
        self.assertTrue(result.operations[0].success, agent.last_citation_gate_report)
        self.assertFalse(bank.entries)
        self.assertEqual(agent.pending_receipt['operations'][0]['outcome'], 'committed')
        delivered_id=agent.pending_receipt['receipt_id']
        agent.prepare_visible_context('next observation',[])
        asyncio.run(agent.process('next observation',2))
        maintenance=[kw for phase,kw in requests if phase=='maintenance'][-1]
        self.assertIn(delivered_id,maintenance['prompt'])
        self.assertEqual(agent.receipt_deliveries[-1]['status'],'response_received_consumed')

    def test_gap_delete_requires_reason_exact_quote_and_one_repair(self):
        bank = LatestEvidenceGapMemory(); key = bank.save_gap('Tool not installed.')
        bad={'memory_id':key,'reason':'Resolved','evidence':[{'quote':'not present'}]}
        agent, result, requests = self._cycle([('memory_delete',bad)], [], bank=bank)
        self.assertFalse(result.operations[0].success)
        self.assertEqual([phase for phase,_ in requests].count('citation_review'), 0)
        good={'memory_id':key,'reason':'Resolved','evidence':[{'quote':TEXT}]}
        agent, result, requests = self._cycle([('memory_delete',good)],
            [['Tool installed.'], batch('insufficient'), ['Tool installed.'], batch()], bank=bank,
            repair_limit=1, repairs=[{'decision':'replace','content':'Receipt confirms installation.',
                                      'evidence':[{'quote':TEXT}]}])
        self.assertTrue(result.operations[0].success, agent.last_citation_gate_report)
        self.assertEqual([phase for phase,_ in requests].count('citation_review'), 4)
        self.assertEqual([phase for phase,_ in requests].count('citation_repair'), 1)
        self.assertEqual(agent.pending_receipt['operations'][0]['outcome'], 'committed_after_repair')

    def test_malformed_delete_evidence_is_local_and_preserves_independent_write(self):
        for evidence in ([{}], [{'quote': 7}]):
            with self.subTest(evidence=evidence):
                bank=LatestEvidenceGapMemory(); key=bank.save_gap('Old gap.')
                calls=[('memory_delete',{'memory_id':key,'reason':'Resolved.',
                                         'evidence':evidence}),
                       ('memory_save_knowledge',{'content':'Independent fact.',
                                                 'evidence':[{'quote':TEXT}]})]
                agent,result,requests=self._cycle(calls,[['Independent fact.'],batch()],bank=bank)
                rows=agent.last_citation_gate_report['operations']
                self.assertFalse(result.operations[0].success)
                self.assertTrue(result.operations[1].success,rows)
                self.assertEqual(bank.entries[0].id,key)
                self.assertEqual(bank.knowledge[0].content,'Independent fact.')
                self.assertEqual(rows[0]['preparation'],'citation_set_not_eligible')
                self.assertIn('invalid_evidence_item',rows[0]['input']['preparation']['issues'])
                self.assertEqual([p for p,_ in requests].count('citation_review'),2)

    def test_malformed_delete_split_or_batch_is_local_and_does_not_skip_sibling(self):
        for malformed in ({'claims':['wrong schema']},
                          {'overall':judgment(),'results':[]}):
            with self.subTest(malformed=malformed):
                bank=LatestEvidenceGapMemory(); key=bank.save_gap('Old gap.')
                calls=[('memory_delete',{'memory_id':key,'reason':'Resolved.',
                                         'evidence':[{'quote':TEXT}]}),
                       ('memory_save_knowledge',{'content':'Independent fact.',
                                                 'evidence':[{'quote':TEXT}]})]
                first=[malformed] if 'claims' in malformed else [['Gap resolved.'],malformed]
                agent,result,_=self._cycle(calls,first+[['Independent fact.'],batch()],bank=bank)
                rows=agent.last_citation_gate_report['operations']
                self.assertFalse(result.operations[0].success)
                self.assertTrue(result.operations[1].success,rows)
                self.assertEqual(rows[0]['failure_scope'],'operation_local')
                self.assertIn('Resolved.',rows[0]['explanation'])
                self.assertEqual(bank.entries[0].id,key)
                self.assertEqual(bank.knowledge[0].content,'Independent fact.')

    def test_malformed_delete_split_uses_at_most_one_repair(self):
        bank=LatestEvidenceGapMemory(); key=bank.save_gap('Old gap.')
        calls=[('memory_delete',{'memory_id':key,'reason':'Resolved.',
                                 'evidence':[{'quote':TEXT}]})]
        agent,result,requests=self._cycle(calls,[{'claims':['wrong']},{'claims':['still wrong']}],
            bank=bank,repair_limit=1,repairs=[{'decision':'replace','content':'Still resolved.',
                                                'evidence':[{'quote':TEXT}]}])
        self.assertFalse(result.operations[0].success)
        self.assertEqual(bank.entries[0].id,key)
        self.assertEqual([p for p,_ in requests].count('citation_repair'),1)
        self.assertEqual([p for p,_ in requests].count('citation_review'),2)

    def test_malformed_delete_evidence_does_not_mask_source_corruption(self):
        from gap_evidence import SourceScopeError
        bank=LatestEvidenceGapMemory(); key=bank.save_gap('Old gap.')
        calls=[('memory_delete',{'memory_id':key,'reason':'Resolved.',
                                 'evidence':[{}]}),
               ('memory_save_knowledge',{'content':'Independent fact.',
                                         'evidence':[{'quote':TEXT}]})]
        with patch('gap_evidence_alignment._validate_catalog',
                   side_effect=SourceScopeError('invalid_visible_source')):
            agent,result,requests=self._cycle(calls,[],bank=bank)
        rows=agent.last_citation_gate_report['operations']
        self.assertFalse(result.operations[0].success)
        self.assertFalse(result.operations[1].success)
        self.assertEqual(rows[0]['engineering_status'],'host_error')
        self.assertEqual([p for p,_ in requests].count('citation_review'),0)
        self.assertEqual(bank.entries[0].id,key)

    def test_non_v4_maintenance_system_request_is_baseline_exact(self):
        from latest_evidence_gap_agent import latest_phase1_system
        expected=latest_phase1_system().replace(
            'Every valid save becomes the latest content regardless of binding.',
            'A save becomes latest only after exact submitted citations pass the host review gate.').replace(
            'Malformed evidence records binding error while valid content is still committed;',
            'Malformed evidence prevents publication;').replace('Use no extra review phase.',
            'Host review is separate from your maintenance proposal.')
        expected+='\nHost gate: missing/non-exact citations are not publishable. Deletes are not executed because this tool has no citation protocol. A later host commit receipt states what actually changed.\n'
        for strategy in (ONE_SENTENCE,v3.STRATEGY):
            with self.subTest(strategy=strategy):
                _,_,requests=self._cycle([],[],review_strategy=strategy)
                maintenance=next(kw for phase,kw in requests if phase=='maintenance')
                self.assertEqual(maintenance['system'],expected)
                self.assertIn(TEXT,maintenance['prompt'])

    def test_delete_target_change_during_review_is_not_published(self):
        bank=LatestEvidenceGapMemory(); key=bank.save_gap('old gap')
        args={'memory_id':key,'reason':'resolved','evidence':[{'quote':TEXT}]}
        calls=[]
        async def fake(**kwargs):
            phase=agent.transport_phase; calls.append(phase)
            if phase=='maintenance':return reply([('memory_delete',args)])
            if phase=='selection':return reply(content='<no_intervention/>')
            if len([p for p in calls if p=='citation_review'])==2:
                bank.save_gap('separate gap')
                return reply(content=json.dumps(batch()))
            return reply(content=json.dumps(['The gap was resolved.']))
        agent=CitationGateMemoryAgent(task='synthetic',memory=bank,llm=NS(call=fake),
                                     review_strategy=v4.STRATEGY)
        agent.prepare_visible_context('UNQUOTED OBSERVATION',[{'source_id':'e1','role':'tool_observation',
            'order':1,'field_path':'result','text':TEXT,'record_digest':sha256(TEXT),
            'record_digest_kind':'event'}])
        result=asyncio.run(agent.process('UNQUOTED OBSERVATION',1))
        self.assertFalse(result.operations[0].success)
        self.assertEqual(bank.entries[0].id,key)

    def test_v4_write_repair_and_v3_schema_unchanged(self):
        args={'content':'The file exists.','evidence':[{'quote':TEXT}]}
        agent,result,requests=self._cycle([('memory_save_knowledge',args)],
            [['The file exists.'],batch('insufficient'),
             ['The file was created.'],batch()],repair_limit=1,
            repairs=[{'decision':'replace','content':'The file was created.',
                      'evidence':[{'quote':TEXT}]}])
        self.assertTrue(result.operations[0].success,agent.last_citation_gate_report)
        self.assertEqual(agent.memory.knowledge[0].content,'The file was created.')
        self.assertEqual([p for p,_ in requests].count('citation_review'),4)
        self.assertEqual([p for p,_ in requests].count('citation_repair'),1)
        self.assertEqual(v3.STRATEGY,'claim-split-same-evidence-v3')

    def test_frozen_small_comparison_materials_and_delete_na(self):
        dataset=Path(__file__).resolve().parents[1]/'benchmark'/'candidate_data'
        a,b=plan(dataset,v3.STRATEGY),plan(dataset,v4.STRATEGY)
        self.assertEqual(len(a['entries']),13)
        self.assertEqual([x['material_sha256'] for x in a['entries']],
                         [x['material_sha256'] for x in b['entries']])
        self.assertEqual(sum(x['preparation']=='not_applicable_delete_v3' for x in a['entries']),2)
        self.assertTrue(all('submitted_evidence' not in x['initial_request']['prompt']
                            for x in b['entries']))
