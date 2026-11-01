"""Real prepare/worker in fake mode; no launcher, container, task or LLM."""
import asyncio
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from pma_evidence_review.tests.test_bank_display import STAGE
from pma_evidence_review.tests.no_network import install_guard
from citation_gate_config import BANK_DISPLAY_POLICY, maintenance_source_paths, verify_gate_sources


class BankDisplayPrepareTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_real_frontend_plan_actual_prepare_freezes_policy_and_current_sources(self):
        from experiment_runner.__main__ import build_plan
        from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import prepare_six_task_manifest as pm, single_run as sr
        from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_official_evaluator import COMMIT
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            task, memory = root/'task.py', root/'memory.json'
            task.write_text("native_claude_cc_vibe_opus48={'model':'claude-opus-4-8'}\n")
            memory.write_text(json.dumps({'claude_monitor_opus48':{'model':'claude-opus-4-8'}}))
            value = {'schema':'ga-experiment-plan-v1','method':'pma-gap',
                'slots':[{'task':'sqlite-with-gcov'}], 'runtime_policy':{},
                'memory_maintenance_policy':BANK_DISPLAY_POLICY,
                'dataset':{'source_git':str(root),'commit':COMMIT},
                'environment':{'fake_only':True,'profiles':{'task_profile_file':str(task),'pma_profile_file':str(memory)}}}
            public = {'tasks':[{'task':'sqlite-with-gcov','agent_timeout_sec':900,'verifier_timeout_sec':900}]}
            with patch('experiment_runner.__main__.catalog', return_value=public):
                plan = build_plan(value)
            self.assertEqual(plan['config']['memory_maintenance_policy'], BANK_DISPLAY_POLICY)
            desc = {'image_tag':'synthetic:v1','public_members':[], 'evaluator_members':[],
                    'native_agent_seconds':900,'native_verifier_seconds':900}
            stack.enter_context(patch.object(pm,'descriptor',return_value=desc))
            def materialize(source,name,public,members,**kw):
                public.mkdir()
            def export(source,name,tests,**kw):
                (tests/'test.sh').write_text('true\n')
            stack.enter_context(patch.object(pm,'materialize_public',side_effect=materialize))
            stack.enter_context(patch.object(pm,'export_task',side_effect=export))
            stack.enter_context(patch.object(pm,'image_identity',return_value={
                'repo_digests':['synthetic@sha256:'+'0'*64],'image_id':'synthetic','platform':'linux/amd64'}))
            args = NS(task='sqlite-with-gcov',condition='B',occurrence=1,fake_only=True,
                research_candidate='pma_gap_memory_v0',memory_maintenance_policy=BANK_DISPLAY_POLICY,
                runtime_policy={},official_source_git=str(root),task_profile_file=str(task),
                pma_profile_file=str(memory),output=str(root/'new'))
            result = sr.prepare(args)
            frozen = json.loads((root/'new/manifest.json').read_text())['config']
            self.assertEqual(frozen['memory_maintenance_policy'],BANK_DISPLAY_POLICY)
            self.assertEqual(set(frozen['maintenance_source_sha256']),set(maintenance_source_paths(BANK_DISPLAY_POLICY)))
            self.assertNotIn('citation_review_gate',frozen)
            self.assertNotIn('citation_review_strategy',frozen)
            verify_gate_sources(frozen)
            self.assertFalse(result['execution_authorized'])

    def test_real_worker_fake_ready_policy_and_before_call_delivery(self):
        from worker_main import serve
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requests,responses=root/'spool/in',root/'spool/out'
            requests.mkdir(parents=True); responses.mkdir()
            events=[('task_start',{'initial_user_content':'Synthetic task'}),
                    ('before_actor_call',{'actor_attempt':1}),('task_end',{'terminal':'synthetic-stop'})]
            for seq,(kind,fields) in enumerate(events,1):
                row=dict(schema='pma-ga-events-v1',kind=kind,sequence=seq,event_id=f'e{seq}',
                         run_id='offline',task_id='synthetic',**fields)
                (requests/f'e{seq}.json').write_text(json.dumps(row))
            args=NS(private_root=str(root/'private'),requests=str(requests),responses=str(responses),
                run_id='offline',task_id='synthetic',fake_memory=True,deadline_epoch=None,
                research_candidate='pma_gap_memory_v0',memory_maintenance_policy=BANK_DISPLAY_POLICY)
            asyncio.run(serve(args))
            ready=json.loads((root/'private/worker_ready.json').read_text())
            self.assertEqual(ready['memory_maintenance_policy'],BANK_DISPLAY_POLICY)
            self.assertEqual(json.loads((responses/'e2.json').read_text())['result']['status'],'reminder')
            phases=[json.loads(line)['phase'] for line in (root/'private/archive/memory_payload.jsonl').read_text().splitlines()]
            self.assertEqual(phases,['maintenance','selection'])
