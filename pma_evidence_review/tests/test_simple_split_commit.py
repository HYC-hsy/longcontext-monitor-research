"""Scripted live v3 multiple-origin publication regression; no semantic inference."""
import json
import unittest
from pma_evidence_review.tests.no_network import install_guard


class SimpleCommitTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_live_multiple_origins_can_commit_without_claim_or_evidence_ids(self):
        import asyncio
        from types import SimpleNamespace as NS
        from pma_evidence_review import claim_split_simple as simple
        from pma_evidence_review.tests import test_live_gate as host
        material = []

        async def fake(**kw):
            if agent.transport_phase == 'maintenance':
                return host.reply([host.write('The quoted observation was recorded.')])
            if agent.transport_phase == 'selection':
                return host.reply(content='<no_intervention/>')
            if kw['prompt'].startswith('CLOSED MATERIAL'):
                material.append(json.loads(kw['prompt'].split('\n', 1)[1]))
                return host.reply(content=json.dumps(['The quoted observation was recorded.']))
            return host.reply(content=json.dumps({
                'overall': {'verdict': 'supported', 'reason': 'Scripted test only.'},
                'results': [{'verdict': 'supported', 'reason': 'Scripted test only.'}]}))

        bank = host.LatestEvidenceGapMemory()
        agent = host.CitationGateMemoryAgent(task='synthetic', memory=bank,
                    llm=NS(call=fake), review_strategy=simple.STRATEGY)
        events = [{'source_id': 'event' + str(i), 'role': role, 'order': i,
                   'field_path': field, 'text': host.TEXT,
                   'record_digest': host.sha256(host.TEXT), 'record_digest_kind': 'event'}
                  for i, (role, field) in enumerate([
                      ('tool_command', 'commands/0'), ('tool_observation', 'stdout')], 1)]
        agent.prepare_visible_context('UNQUOTED SECRET', events)
        result = asyncio.run(agent.process('UNQUOTED SECRET', 1))
        self.assertTrue(result.operations[0].success, agent.last_citation_gate_report)
        self.assertEqual(bank.knowledge[0].content, 'The quoted observation was recorded.')
        attempt = agent.last_citation_gate_report['operations'][0]['attempts'][0]
        self.assertEqual(attempt['input']['alignment']['status'], 'exact_multiple')
        self.assertEqual(attempt['input']['preparation']['status'], 'ready')
        groups = material[0]['submitted_evidence']
        self.assertEqual(len(groups), 1)
        self.assertEqual({o['role'] for o in groups[0]['alternative_origins']},
                         {'tool_command', 'tool_observation'})
        self.assertNotIn('UNQUOTED SECRET', json.dumps(material))
        self.assertEqual(agent.pending_receipt['operations'][0]['outcome'], 'committed')
        bank.validate_bank()


if __name__ == '__main__':
    unittest.main()
