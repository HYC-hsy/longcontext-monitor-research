"""Exercise real batch gate preflight; never launch a Task or subprocess."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import batch_controller as bc
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import citation_gate_config as cfg
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import gate_certification as gc
from experiment_runner.runtime_policy import resolve_policy

ROOT=Path(__file__).resolve().parents[2]

class GateBatchPreflightTests(unittest.TestCase):
    def setup_records(self, root, mode, fixture):
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        asset={'native_agent_seconds':900,'native_verifier_seconds':900}
        policy=resolve_policy({'agent_timeout':'uncapped','task_turns':'uncapped','verifier_timeout':'official'},asset,{'task_turns_max':None})
        row={'order':1,'task':'sqlite-with-gcov','repeat':1,'condition':'B','research_candidate':'pma_gap_evidence_v1'}
        config={'research_candidate':row['research_candidate'],'citation_review_gate':mode,'runtime_policy':policy,
                'citation_gate_source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()for p in cfg.gate_source_paths()}}
        h=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        manifest={'schema':'pma-ga-live-manifest-v5','execution_authorized':False,'planned_order':[row],
                  'config':config,'config_sha256':h,'assets':{row['task']:asset}}
        if fixture:manifest['zero_model_fixture_only']=True
        mp=root/'manifest.json';mp.write_text(json.dumps(manifest),encoding='utf-8')
        bound={**row,'run_id':'synthetic-run','batch_id':'synthetic-run','run_root':str(root/'runs/synthetic-run'),'config_sha256':h}
        grant={'execution_authorized':True,'manifest_sha256':hashlib.sha256(mp.read_bytes()).hexdigest(),
               'audited_code_commit':head,'approved_arms':[row],'run_bindings':[bound],'run_id':bound['run_id'],
               'batch_id':bound['batch_id'],'config_sha256':h,'output_root':str(root/'runs')}
        if fixture:grant['zero_model_fixture_only']=True
        ap=root/'authorization.json';ap.write_text(json.dumps(grant),encoding='utf-8')
        # No paths beyond preflight are supplied: sentinel stops before them.
        return NS(manifest=str(mp),authorization=str(ap),zero_model_fixture=fixture,
                  candidate_profile_fixture=False,stateful_fake_replies=None,batch_result=str(root/'result.json'))

    def test_both_fake_modes_pass_real_gate_policy_and_authorization_preflight(self):
        for mode in cfg.MODES:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                args=self.setup_records(Path(tmp),mode,True)
                actual=bc.verify_live_spec
                seen=[]
                def inspect(spec):
                    self.assertEqual(spec['citation_review_gate'],mode)
                    self.assertIs(spec['zero_model_fixture_only'],True)
                    actual(spec)  # real gate/source/policy/authorization validation
                    seen.append(spec)
                    raise RuntimeError('validated_before_runtime')
                with patch.object(bc,'verify_live_spec',side_effect=inspect):
                    with self.assertRaisesRegex(RuntimeError,'validated_before_runtime'):bc.run_batch(args)
                self.assertEqual(len(seen),1)
                self.assertFalse(Path(args.batch_result).exists())
                self.assertFalse((Path(tmp)/'runs').exists())

    def test_real_gate_cannot_use_fake_certificate_exemption(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.setup_records(Path(tmp),'gate-only',False)
            with self.assertRaisesRegex(ValueError,'gate_certificate_required'):bc.run_batch(args)
            self.assertFalse((Path(tmp)/'runs').exists())

    def test_inconsistent_fake_flag_rejected_before_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.setup_records(Path(tmp),'gate-one-repair',True)
            args.zero_model_fixture=False
            with patch.object(bc,'verify_live_spec',side_effect=AssertionError('should not validate')):
                with self.assertRaisesRegex(RuntimeError,'fixture identity mismatch'):bc.run_batch(args)
