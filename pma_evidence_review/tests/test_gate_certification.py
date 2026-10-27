"""Actual synthetic worker captures plus mutation tests; never a model/profile."""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from pma_evidence_review.tests.test_live_gate import ROOT, STAGE
from pma_evidence_review.tests.no_network import install_guard
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import gate_certification as gc


def write_json(path,value):path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
def read_json(path):return json.loads(path.read_text(encoding='utf-8'))
def change_lines(path,fn):
    rows=[json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
    fn(rows);path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')


class GateCertificateTests(unittest.TestCase):
    def setUp(self):install_guard(self)

    def fixture(self,root,mode):
        import worker_main
        from citation_gate_config import gate_source_paths
        requests=root/'spool/requests';responses=root/'spool/responses'
        requests.mkdir(parents=True);responses.mkdir()
        events=[('task_start',{'initial_user_content':'Synthetic requirement'}),
                ('before_actor_call',{'actor_attempt':1}),
                ('actor_step',{'actor_attempt':1,'step_status':'normal','commands':['synthetic command'],
                               'response':'Synthetic public response','observation':json.dumps({'content':'Synthetic public response','tool_results':[{'tool_use_id':'t1','content':'Synthetic public observation'}]})}),
                ('task_end',{'terminal':{'synthetic':True}})]
        for n,(kind,extra) in enumerate(events,1):
            write_json(requests/f'e{n}.json',{'schema':'pma-ga-events-v1','kind':kind,'sequence':n,
                'event_id':f'e{n}','run_id':'r','task_id':'synthetic',**extra})
        args=NS(private_root=str(root/'private'),requests=str(requests),responses=str(responses),run_id='r',
                task_id='synthetic',fake_memory=True,deadline_epoch=None,research_candidate='pma_gap_evidence_v1',
                citation_review_gate=mode)
        with patch.dict(os.environ,{'PMA_MEMORY_PROFILE_FILE':''}):asyncio.run(worker_main.serve(args))
        base=root/'private/archive'
        write_json(base/'execution_identity.json',{'gate_config':{'citation_review_gate':mode,
            'citation_gate_source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in gate_source_paths()}},
            'gate_certificate_source_sha256':gc.source_identity()})
        return base

    def test_real_worker_evidence_accepted_both_modes(self):
        for mode in ('gate-only','gate-one-repair'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                base=self.fixture(Path(tmp),mode)
                certificate=gc.inspect_evidence(base,mode)
                write_json(base/'gate_certificate.json',certificate)
                self.assertEqual(gc.verify_certificate(base,mode),certificate)
                self.assertEqual(certificate['receipts_delivered'],1)
                self.assertTrue(certificate['accepted_revisions']);self.assertTrue(certificate['rejected_revisions'])
                self.assertEqual(certificate['repair_calls'],2 if mode=='gate-one-repair' else 0)

    def test_mutated_evidence_fails_not_just_phase_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=self.fixture(Path(tmp),'gate-only')
            original={p:p.read_bytes() for p in base.iterdir() if p.is_file()}
            mutations=[
                lambda:change_lines(base/'gap_cycle.jsonl',lambda r:r[0]['citation_gate_report'].update(operations=[])),
                lambda:change_lines(base/'gap_cycle.jsonl',lambda r:r[0]['citation_gate_report']['operations'][1].update(success=True)),
                lambda:change_lines(base/'memory_payload.jsonl',lambda r:r[-2].update(prompt='missing receipt')),
                lambda:change_lines(base/'gap_cycle.jsonl',lambda r:r[1]['citation_gate_report'].update(prior_receipt_deliveries=[])),
                lambda:change_lines(base/'gap_cycle.jsonl',lambda r:r[0]['citation_gate_report']['operations'][0]['attempts'][0]['request'].update(prompt='unbound evidence')),
                lambda:write_json(base/'execution_identity.json',{'gate_config':{'citation_review_gate':'gate-one-repair'}}),
                lambda:write_json(base/'execution_identity.json',{**read_json(base/'execution_identity.json'),
                    'gate_certificate_source_sha256':{}}),
                lambda:change_lines(base/'gap_cycle.jsonl',lambda r:r[0]['citation_gate_report']['operations'][0]['attempts'][0]['input']['host_provenance']['sources'][0]['slices'][0].update(text='extra unobserved evidence')),
                lambda:change_lines(base/'memory_payload.jsonl',lambda r:r[-1].update(prompt=r[-1]['prompt']+'GATE_FIXTURE_REJECTED')),
            ]
            for mutate in mutations:
                for p,b in original.items():p.write_bytes(b)
                mutate()
                with self.assertRaises((ValueError,KeyError)):gc.inspect_evidence(base,'gate-only')
            for p,b in original.items():p.write_bytes(b)
            with self.assertRaises(FileNotFoundError):gc.verify_certificate(base,'gate-only')
            cert=gc.inspect_evidence(base,'gate-only');cert['source_sha256']={}
            write_json(base/'gate_certificate.json',cert)
            with self.assertRaisesRegex(ValueError,'certificate_mismatch'):gc.verify_certificate(base,'gate-only')

    def test_launch_rejects_baseline_certificate_or_wrong_gate(self):
        for config in ({'citation_review_gate':'gate-only'},{'citation_review_gate':'gate-one-repair'}):
            with self.assertRaisesRegex(ValueError,'certificate_required'):
                gc.require_launch_certificate({'config':config,'native_shared_certification':{'evidence':{}}})
        gc.require_launch_certificate({'config':{}})
        with self.assertRaisesRegex(ValueError,'fixture_identity'):
            gc.require_launch_certificate({'config':{'citation_review_gate':'gate-only'}},fixture=True)
        gc.require_launch_certificate({'config':{'citation_review_gate':'gate-only'},'zero_model_fixture_only':True},fixture=True)

    def test_baseline_phase_contract_stays_strict(self):
        from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run_certification import require_gap_phases
        require_gap_phases(['maintenance','selection'])
        with self.assertRaisesRegex(RuntimeError,'non-two-stage'):
            require_gap_phases(['maintenance','citation_review','selection'])
        with self.assertRaisesRegex(RuntimeError,'phase contract'):
            require_gap_phases(['maintenance','selection'],'gate-only')
        with self.assertRaisesRegex(RuntimeError,'phase contract'):
            require_gap_phases(['maintenance','citation_review','selection'],'gate-one-repair')

    def test_fixture_parser_passes_explicit_mode(self):
        from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import single_run_fixture as sf
        for mode in ('gate-only','gate-one-repair'):
            args=['fixture','--task','sqlite-with-gcov','--condition','B','--research-candidate','pma_gap_evidence_v1',
                  '--citation-review-gate',mode,'--output','unused']
            for key in ('official-source-git','task-profile-file','ga-source','runtime-root','worker-python',
                        'harbor-python','bench-root','harbor-source-root','pma-profile-file'):
                args += ['--'+key,'unused']
            with patch('sys.argv',args),patch.object(sf,'prepare',side_effect=RuntimeError('stop_before_assets')) as prepare:
                with self.assertRaisesRegex(RuntimeError,'stop_before_assets'):sf.main()
                ns=prepare.call_args.args[0]
                self.assertEqual(ns.citation_review_gate,mode);self.assertTrue(ns.fake_only)

    def test_formal_prepare_refuses_missing_gate_certificate_before_assets(self):
        from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import single_run as sr
        args=NS(task='sqlite-with-gcov',condition='B',research_candidate='pma_gap_evidence_v1',
                citation_review_gate='gate-only',fake_only=False)
        with self.assertRaisesRegex(ValueError,'certification-dir required'):sr.prepare(args)
