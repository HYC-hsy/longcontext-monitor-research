"""Offline strategy identity checks; fake fixtures do not assert semantic quality."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import citation_gate_config as cfg
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import gate_certification as cert
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import single_run as sr
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import single_run_fixture as sf
from pma_evidence_review.tests.no_network import install_guard


class ClaimSplitPolicyTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_default_direct_and_explicit_worker_switch(self):
        self.assertEqual(cfg.validate_strategy('gate-only'),cfg.STRATEGY)
        self.assertEqual(cfg.worker_flags('gate-only','pma_gap_evidence_v1'),
                         ['--citation-review-gate','gate-only'])
        self.assertEqual(cfg.worker_flags('gate-one-repair','pma_gap_evidence_v1',cfg.CLAIM_SPLIT),
                         ['--citation-review-gate','gate-one-repair',
                          '--citation-review-strategy',cfg.CLAIM_SPLIT])
        self.assertEqual(cfg.worker_flags(None,'U'),[])
        for mode,strategy in ((None,cfg.CLAIM_SPLIT),('gate-only','unknown'),
                              ('gate-only',False)):
            with self.subTest(mode=mode,strategy=strategy),self.assertRaises(ValueError):
                cfg.validate_strategy(mode,strategy)

    def test_binding_rejects_dropped_or_changed_strategy(self):
        for requested,stored in ((None,cfg.CLAIM_SPLIT),(cfg.CLAIM_SPLIT,None),
                                 (cfg.STRATEGY,cfg.CLAIM_SPLIT)):
            config={'citation_review_gate':'gate-only'}
            if stored is not None:config['citation_review_strategy']=stored
            with self.assertRaisesRegex(ValueError,'strategy differs'):
                cfg.require_strategy_binding(requested,config,'gate-only')
        self.assertEqual(cfg.require_strategy_binding(None,
            {'citation_review_gate':'gate-only'},'gate-only'),cfg.STRATEGY)

    def test_launch_rejects_strategy_without_gate(self):
        with self.assertRaisesRegex(ValueError,'explicit gate'):
            cert.require_launch_certificate({'config':{'citation_review_strategy':cfg.CLAIM_SPLIT}})

    def test_source_binding_includes_reused_vendor_bytes(self):
        paths=cfg.gate_source_paths()
        for path in ('pma_evidence_review/vendor/rag_models.py',
                     'pma_evidence_review/vendor/rag_prompts.py',
                     'pma_evidence_review/vendor/sourcecheck_types.py',
                     'pma_evidence_review/vendor/prompts/claim-extraction-system.txt'):
            self.assertIn(path,paths)
        self.assertEqual(len(paths),len(set(paths)))

    def test_invalid_strategy_fails_before_output_or_profile(self):
        args=NS(task='fix-ocaml-gc',condition='B',research_candidate='pma_gap_evidence_v1',
                citation_review_gate='gate-only',citation_review_strategy='invalid',
                output='unused',runtime_policy={},fake_only=True)
        with patch.object(Path,'mkdir',side_effect=AssertionError('created output')):
            with self.assertRaisesRegex(ValueError,'valid strategy'):
                sr.prepare(args)

    def test_fixture_cli_propagates_candidate_to_prepare(self):
        argv=['fixture','--task','fix-ocaml-gc','--condition','B',
              '--research-candidate','pma_gap_evidence_v1','--citation-review-gate','gate-only',
              '--citation-review-strategy',cfg.CLAIM_SPLIT,'--output','unused']
        for key in ('official-source-git','task-profile-file','ga-source','runtime-root',
                    'worker-python','harbor-python','bench-root','harbor-source-root','pma-profile-file'):
            argv+=['--'+key,'unused']
        with patch('sys.argv',argv),patch.object(sf,'prepare',side_effect=RuntimeError('stop')) as prepare:
            with self.assertRaisesRegex(RuntimeError,'stop'):sf.main()
            self.assertEqual(prepare.call_args.args[0].citation_review_strategy,cfg.CLAIM_SPLIT)

    def test_old_direct_and_candidate_certificates_not_interchangeable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'execution_identity.json'
            for expected,actual in ((cfg.CLAIM_SPLIT,None),(None,cfg.CLAIM_SPLIT)):
                config={'citation_review_gate':'gate-only'}
                if actual is not None:config['citation_review_strategy']=actual
                path.write_text(json.dumps({'gate_config':config}),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'strategy differs'):
                    cert.inspect_evidence(tmp,'gate-only',expected)

    def test_harbor_spec_cannot_drop_candidate_switch(self):
        from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.pma_harbor_hooks import verify_live_spec
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=root/'manifest.json';authorization=root/'authorization.json'
            manifest.write_text(json.dumps({'config':{'citation_review_gate':'gate-only',
                'citation_review_strategy':cfg.CLAIM_SPLIT}}),encoding='utf-8')
            authorization.write_text('{}',encoding='utf-8')
            spec={'schema':'pma-ga-live-run-v1','mode':'authorized_live',
                  'manifest_path':str(manifest),'authorization_path':str(authorization),
                  'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
                  'authorization_sha256':hashlib.sha256(authorization.read_bytes()).hexdigest(),
                  'research_candidate':'pma_gap_evidence_v1','condition':'B',
                  'citation_review_gate':'gate-only'}
            with self.assertRaisesRegex(ValueError,'strategy differs'):verify_live_spec(spec)

    def test_frontend_rejects_candidate_switch_without_evidence_gate(self):
        from experiment_runner.__main__ import build_plan
        config={'schema':'ga-experiment-plan-v1','method':'pma-gap-evidence',
                'slots':[{'task':'fix-ocaml-gc'}], 'citation_review_strategy':cfg.CLAIM_SPLIT,
                'dataset':{}}
        with self.assertRaisesRegex(ValueError,'explicit gate'):build_plan(config)
        config['citation_review_gate']='gate-only';config['method']='ga-only'
        with self.assertRaisesRegex(ValueError,'B carrier'):build_plan(config)


    def test_actual_single_plan_and_manifest_bind_candidate(self):
        from pma_evidence_review.tests.test_gate_policy_preflight import GatePolicyPreflightTests
        harness=GatePolicyPreflightTests('test_actual_prepare_plan_manifest_identity_chain_for_both_modes')
        original_args=harness.args
        harness.args=lambda root,**changes:original_args(root,citation_review_strategy=cfg.CLAIM_SPLIT,**changes)
        original_write=sr._write_new;records=[]
        def write(path,value):
            if path.name in ('plan.json','manifest.json'):records.append((path.name,value))
            original_write(path,value)
        with patch.object(sr,'_write_new',side_effect=write):
            harness.test_actual_prepare_plan_manifest_identity_chain_for_both_modes()
        self.assertEqual(len(records),4)
        for name,value in records:
            self.assertEqual((value if name=='plan.json' else value['config'])[
                'citation_review_strategy'],cfg.CLAIM_SPLIT)

    def test_frontend_freezes_and_forwards_candidate_policy(self):
        from experiment_runner.__main__ import build_plan,execute,succeeded
        from experiment_runner.test_runner_frontend import FakeBackend
        from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_official_evaluator import COMMIT
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            config={'schema':'ga-experiment-plan-v1','method':'pma-gap-evidence',
                'slots':[{'task':'fix-ocaml-gc'}], 'runtime_policy':{},
                'citation_review_gate':'gate-one-repair','citation_review_strategy':cfg.CLAIM_SPLIT,
                'dataset':{'source_git':str(root),'commit':COMMIT},
                'environment':{'fake_only':True,'profiles':{
                    'task_profile_file':'/unused-task','pma_profile_file':'/unused-memory'}}}
            public={'tasks':[{'task':'fix-ocaml-gc','agent_timeout_sec':900,'verifier_timeout_sec':900}]}
            with patch('experiment_runner.__main__.catalog',return_value=public):plan=build_plan(config)
            for dropped in (False,True):
                backend=FakeBackend();original=backend.prepare
                def prepare(args):
                    outcome=original(args)
                    directory=Path(args.output)
                    for name in ('plan.json','manifest.json'):
                        path=directory/name;value=json.loads(path.read_text())
                        target=value if name=='plan.json' else value.setdefault('config',{})
                        target['citation_review_gate']=args.citation_review_gate
                        if not dropped:target['citation_review_strategy']=args.citation_review_strategy
                        path.write_text(json.dumps(value))
                    return outcome
                backend.prepare=prepare
                rows=execute(plan,root/str(dropped),'prepare',backend)
                self.assertEqual(backend.prepared[0].citation_review_strategy,cfg.CLAIM_SPLIT)
                if dropped:
                    self.assertEqual(rows[0]['status'],'preparation_failed')
                    self.assertIn('strategy differs',rows[0]['error'])
                else:self.assertTrue(succeeded(rows,1,'prepare'))


if __name__=='__main__':unittest.main()
