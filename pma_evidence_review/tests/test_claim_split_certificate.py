"""Actual offline worker capture and replay; no model or Task is executed."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pma_evidence_review.tests import test_gate_certification as base
from pma_evidence_review.tests.no_network import install_guard
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import citation_gate_config as cfg


class ClaimSplitCertificateTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def fixture(self,root,mode):
        import worker_main
        original=worker_main.serve
        async def candidate(args):
            args.citation_review_strategy=cfg.CLAIM_SPLIT
            await original(args)
        with patch.object(worker_main,'serve',side_effect=candidate):
            directory=base.GateCertificateTests.fixture(self,root,mode)
        path=directory/'execution_identity.json';execution=base.read_json(path)
        execution['gate_config']['citation_review_strategy']=cfg.CLAIM_SPLIT
        base.write_json(path,execution)
        return directory

    def test_candidate_worker_certifies_each_mode_and_not_direct(self):
        for mode in cfg.MODES:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                directory=self.fixture(Path(tmp),mode)
                certificate=base.gc.inspect_evidence(directory,mode,cfg.CLAIM_SPLIT)
                self.assertEqual(certificate['review_strategy'],cfg.CLAIM_SPLIT)
                self.assertEqual(certificate['receipts_delivered'],1)
                self.assertTrue(certificate['accepted_revisions'])
                self.assertTrue(certificate['rejected_revisions'])
                base.write_json(directory/'gate_certificate.json',certificate)
                self.assertEqual(base.gc.verify_certificate(directory,mode,cfg.CLAIM_SPLIT),certificate)
                with self.assertRaisesRegex(ValueError,'strategy differs'):
                    base.gc.verify_certificate(directory,mode)
                rows=[json.loads(line) for line in (directory/'memory_payload.jsonl').read_text().splitlines()]
                split_count=sum(row['prompt'].startswith('CLOSED MATERIAL') for row in rows)
                batch_rows=[row for row in rows if row['prompt'].startswith('TARGET CONTEXT ONLY')]
                self.assertEqual(split_count,4 if mode=='gate-one-repair' else 3)
                self.assertEqual(len(batch_rows),split_count)
                self.assertEqual(sum(row['phase']=='citation_review' for row in rows),2*split_count)
                for row in batch_rows:
                    context=json.loads(row['prompt'].split('\n',1)[1].split(
                        '\nSUBMITTED EVIDENCE ONLY (unchanged B):\n',1)[0])
                    self.assertEqual(len(context['all_claims']),2)
                    self.assertNotIn('claim_index',context)
                captures=[json.loads(line) for line in (directory/'gap_cycle.jsonl').read_text().splitlines()]
                for cycle in captures:
                    for operation in cycle.get('citation_gate_report',{}).get('operations',[]):
                        for attempt in operation['attempts']:
                            self.assertEqual(len(attempt['claim_reviews']),2)
                            self.assertIn('batch',attempt)
                            self.assertTrue(all('request' not in row for row in attempt['claim_reviews']))

    def test_fenced_repair_replays_existing_strict_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=self.fixture(Path(tmp),'gate-one-repair')
            def cycles(rows):
                for row in rows:
                    for operation in row.get('citation_gate_report',{}).get('operations',[]):
                        if operation.get('repair'):
                            value=operation['repair']
                            value['raw_response']='```json\n'+value['raw_response']+'\n```'
            def responses(rows):
                for row in rows:
                    if row['phase']=='citation_repair':row['content']='```json\n'+row['content']+'\n```'
            base.change_lines(directory/'gap_cycle.jsonl',cycles)
            base.change_lines(directory/'gap_visible_transport.jsonl',responses)
            self.assertEqual(base.gc.inspect_evidence(directory,'gate-one-repair',cfg.CLAIM_SPLIT)[
                'repair_calls'],2)

    def test_candidate_certificate_replays_claims_not_saved_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=self.fixture(Path(tmp),'gate-only')
            path=directory/'gap_cycle.jsonl';raw=path.read_bytes()
            def attempt(rows):return rows[0]['citation_gate_report']['operations'][0]['attempts'][0]
            def batch_response(rows,change):
                record=attempt(rows)['batch']
                value=json.loads(record['raw_response']);change(value)
                record['raw_response']=json.dumps(value)
            mutations=[
                lambda rows:attempt(rows)['claims'][0].update(text='different target'),
                lambda rows:batch_response(rows,lambda value:value.update(decomposition_complete=False)),
                lambda rows:attempt(rows)['claim_reviews'][0].update(evidence_ids=['E999']),
                lambda rows:attempt(rows)['batch']['request'].update(prompt='new evidence'),
                lambda rows:batch_response(rows,lambda value:value['results'].pop()),
                lambda rows:batch_response(rows,lambda value:value['results'][1].update(claim_index=1)),
                lambda rows:batch_response(rows,lambda value:value['results'][0].update(original_fragment='not submitted')),
                lambda rows:attempt(rows)['split'].update(raw_response='{"op_index":0,"claims":[]}'),
                lambda rows:attempt(rows).update(verdict='insufficient'),
            ]
            for mutate in mutations:
                path.write_bytes(raw)
                base.change_lines(path,mutate)
                with self.assertRaises(ValueError):
                    base.gc.inspect_evidence(directory,'gate-only',cfg.CLAIM_SPLIT)
            path.write_bytes(raw)
            self.assertEqual(base.gc.inspect_evidence(directory,'gate-only',cfg.CLAIM_SPLIT)[
                'review_strategy'],cfg.CLAIM_SPLIT)


if __name__=='__main__':unittest.main()
