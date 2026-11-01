"""Real call/delivery contracts with scripted completions, not semantic scoring."""
import ast
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace as NS
import unittest

from pma_evidence_review.tests.test_maintenance_no_review import (
    MaintenanceNoReviewAgent, LatestEvidenceGapMemory, reply, STAGE)
from pma_evidence_review.tests.no_network import install_guard
from citation_gate_config import MAINTENANCE_POLICY, maintenance_source_paths, verify_gate_sources
from episode import construct_upstream, PMAEpisode
from tag_selection_contract import SELECTION_SYSTEM
from verbatim_selection_agent import VerbatimSelectionCitationGateAgent

BASELINE = 'd28d0ed75741f3a627721766a29745ab3ae2da9d'
ROOT = Path(__file__).resolve().parents[2]
REL = STAGE.relative_to(ROOT)
P1_SHA256 = '5ad9ae10f9bdd3573a58c10edc68de153ab5d062562f28e6f79a0862bf987b8e'
P2_SHA256 = 'f8ab207073db662a3af7e712584fdf2bb0433b1c4d42ba9a9e4dae872269d522'


def baseline_bytes(name):
    return subprocess.check_output(['git', 'show', BASELINE + ':' + name], cwd=ROOT)


class SelectionJudgmentPromptTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_real_factory_receives_system_and_delivers_original_text_or_silence(self):
        for raw in ('<no_intervention/>', '<intervene>M1,TASK</intervene>'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                actor = construct_upstream(root / 'upstream', research_candidate='pma_gap_evidence_v1',
                    memory_maintenance_policy=MAINTENANCE_POLICY)
                agent, requests = actor._memory_agent, []
                self.assertIsInstance(agent, MaintenanceNoReviewAgent)
                self.assertNotIn('CitationGateMemoryAgent', [t.__name__ for t in type(agent).__mro__])
                original = '  Preserve the selected worksheet formula.\r\n'
                task = 'Update the specified worksheet only.\r\n'
                async def fake(**kwargs):
                    requests.append((agent.transport_phase, kwargs))
                    if agent.transport_phase == 'maintenance':
                        return reply([('memory_save_knowledge', {'content': original})])
                    self.assertEqual(agent.transport_phase, 'selection')
                    return reply(content=raw)
                actor._memory_llm.call = fake
                episode = PMAEpisode(actor, run_id='offline', task_id='synthetic', archive=root / 'private')
                async def run():
                    await episode.handle(dict(kind='task_start', sequence=1, event_id='e1',
                        run_id='offline', task_id='synthetic', initial_user_content=task))
                    return await episode.handle(dict(kind='before_actor_call', sequence=2, event_id='e2',
                        run_id='offline', task_id='synthetic', actor_attempt=1))
                result = asyncio.run(run())
                self.assertEqual([phase for phase, _ in requests], ['maintenance', 'selection'])
                self.assertEqual(hashlib.sha256(requests[0][1]['system'].encode()).hexdigest(), P1_SHA256)
                self.assertEqual(requests[1][1]['system'], SELECTION_SYSTEM)
                self.assertEqual(hashlib.sha256(requests[1][1]['system'].encode()).hexdigest(), P2_SHA256)
                self.assertNotIn('tools', requests[1][1])
                if raw == '<no_intervention/>':
                    self.assertEqual(result['status'], 'silent')
                    self.assertIsNone(actor._pending_injection)
                else:
                    self.assertEqual(result['status'], 'reminder')
                    wire = result['reminder']
                    blocks, _ = json.JSONDecoder().raw_decode(wire[wire.index('{"blocks":'):])
                    self.assertEqual([b['content'] for b in blocks['blocks']], [original, task])
                    self.assertTrue(agent.pending_refs_valid())
                    actor._memory.active_revisions[agent.last_selection_report['selected'][0]['id']] = 'replaced'
                    self.assertFalse(agent.pending_refs_valid())

    def test_shared_gated_factory_also_receives_the_same_selection_system(self):
        with tempfile.TemporaryDirectory() as tmp:
            actor = construct_upstream(Path(tmp) / 'upstream', research_candidate='pma_gap_evidence_v1',
                citation_review_gate='gate-only', citation_review_strategy='claim-split-same-evidence-v4')
            agent, requests = actor._memory_agent, []
            self.assertIsInstance(agent, VerbatimSelectionCitationGateAgent)
            async def fake(**kwargs):
                requests.append((agent.transport_phase, kwargs))
                return reply() if agent.transport_phase == 'maintenance' else reply(content='<no_intervention/>')
            actor._memory_llm.call = fake
            agent.prepare_visible_context('visible', [])
            asyncio.run(agent.process('visible', 1))
            self.assertEqual([phase for phase, _ in requests], ['maintenance', 'selection'])
            self.assertEqual(requests[1][1]['system'], SELECTION_SYSTEM)

    def test_p2_delta_is_only_system_and_input_protocol_files_are_unchanged(self):
        name = (REL / 'tag_selection_contract.py').as_posix()
        before, after = ast.parse(baseline_bytes(name)), ast.parse((ROOT / name).read_bytes())
        for tree in (before, after):
            found = 0
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(
                        isinstance(t, ast.Name) and t.id == 'SELECTION_SYSTEM' for t in node.targets):
                    node.value = ast.Constant(value='SYSTEM_ONLY')
                    found += 1
            self.assertEqual(found, 1)
        self.assertEqual(ast.dump(before), ast.dump(after))
        for filename in ('latest_evidence_gap_agent.py',
                         'gap_prompts.py', 'verbatim_selection_mixin.py', 'selection_context.py',
                         'evidence_gap_context.py', 'live_launcher.py', 'worker_main.py'):
            name = (REL / filename).as_posix()
            self.assertEqual((ROOT / name).read_bytes(), baseline_bytes(name), filename)

    def test_actual_launch_source_identity_hashes_the_changed_contract(self):
        from experiment_runner.startup import code_identity
        name = (REL / 'tag_selection_contract.py').as_posix()
        files = maintenance_source_paths()
        self.assertEqual(files.count(name), 1)
        config = {'research_candidate': 'pma_gap_evidence_v1',
            'memory_maintenance_policy': MAINTENANCE_POLICY,
            'maintenance_source_sha256': {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in files}}
        verify_gate_sources(config)
        identity = code_identity({'planned_order': [dict(condition='B', research_candidate='pma_gap_evidence_v1')]})
        self.assertEqual(identity['source_files'][name], config['maintenance_source_sha256'][name])
        p1_name = (REL / 'maintenance_no_review_agent.py').as_posix()
        self.assertEqual(identity['source_files'][p1_name], config['maintenance_source_sha256'][p1_name])
        self.assertIn('experiment_runner/startup.py', identity['source_files'])
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            verify_gate_sources({**config, 'maintenance_source_sha256': {}})


    def test_p1_preserves_upstream_save_angles_and_existing_tool_parameters(self):
        from maintenance_no_review_agent import maintenance_system
        source = REL / 'vendor/pma_89e5c0d/src/memory_agent/memory/memory_agent.py'
        raw = (ROOT / source).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
            'e00d412034b8cfebb6b8121477453d2815e26ce2d78344c9f7991a37048e0b35')
        tree = ast.parse(raw)
        originals = {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
            for t in n.targets if isinstance(t, ast.Name)}
        original_p1 = originals['PHASE1_SYSTEM']
        angles = original_p1[original_p1.index('## What to save at Step 1'):].strip()
        self.assertIn(angles, maintenance_system())  # Text preservation, not semantic behavior.
        self.assertEqual(len(maintenance_system()), 4387)
        self.assertEqual(hashlib.sha256(maintenance_system().encode()).hexdigest(), P1_SHA256)
        namespace = {'__name__': 'baseline_maintenance_snapshot'}
        exec(compile(baseline_bytes((REL / 'maintenance_no_review_agent.py').as_posix()),
                     'baseline_maintenance_snapshot.py', 'exec'), namespace)
        old = namespace['MaintenanceNoReviewAgent'](task='task', memory=LatestEvidenceGapMemory(), llm=NS())
        new = MaintenanceNoReviewAgent(task='task', memory=LatestEvidenceGapMemory(), llm=NS())
        def parameters(agent):
            return {tool['function']['name']: tool['function']['parameters'] for tool in agent.get_tools_schema()}
        self.assertEqual(parameters(new), parameters(old))
        # Gated P1 still uses the unchanged latest builder, not this candidate system.
        self.assertEqual((ROOT / REL / 'citation_gate_agent.py').read_bytes(),
                         baseline_bytes((REL / 'citation_gate_agent.py').as_posix()))
