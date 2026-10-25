"""Offline routing and identity checks; no preparation, model or verifier run."""
import hashlib
import importlib
import importlib.util
import os
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiment_runner.__main__ import build_plan, method_environment, DRIVER
from experiment_runner.methods import resolve, candidate_names, validate_binding


class EvidenceGapEntryTests(unittest.TestCase):
    def config(self, method='pma-gap-evidence'):
        return {'schema': 'ga-experiment-plan-v1', 'dataset': {}, 'method': method,
                'slots': [{'task': 'sqlite-with-gcov'}],
                'runtime_policy': {'agent_timeout': 'uncapped',
                                   'task_turns': 'uncapped',
                                   'verifier_timeout': 'official'}}

    def plan(self, config):
        public = {'tasks': [{'task': 'sqlite-with-gcov', 'agent_timeout_sec': 900,
                            'verifier_timeout_sec': 900}]}
        with patch('experiment_runner.__main__.catalog', return_value=public):
            return build_plan(config)

    def test_explicit_mapping_preserves_baseline_policy(self):
        candidate = self.plan(self.config())
        baseline = self.plan(self.config('pma-gap'))
        slot = candidate['slots'][0]
        self.assertFalse(candidate['execution_authorized'])
        self.assertEqual(slot['adapter']['research_candidate'], 'pma_gap_evidence_v1')
        self.assertEqual(slot['adapter']['condition'], 'B')
        self.assertFalse(slot['adapter']['task_complete_response'])
        self.assertEqual(slot['effective_runtime_policy'],
                         baseline['slots'][0]['effective_runtime_policy'])
        self.assertEqual(resolve('pma-gap').research_candidate, 'pma_gap_memory_v0')
        self.assertIn('pma_gap_evidence_v1', candidate_names('B'))
        with self.assertRaises(ValueError):
            validate_binding('A', 'pma_gap_evidence_v1')

    def test_reuse_is_rejected_before_any_source_access(self):
        config = self.config()
        config['runtime_reuse'] = {}
        with self.assertRaisesRegex(ValueError, 'runtime reuse'):
            self.plan(config)
        launcher = importlib.import_module(DRIVER + '.live_launcher')
        with self.assertRaisesRegex(RuntimeError, 'prompt reuse'):
            launcher._require_evaluation_state_contract({
                'schema': 'pma-ga-live-manifest-v5',
                'planned_order': [{'research_candidate': 'pma_gap_evidence_v1'}],
                'native_shared_certification': {'kind': 'verified_prompt_runtime_reuse_v1'}})

    def test_environment_clears_stale_candidate_and_stays_default_off(self):
        inherited = {'GA_PMA_UPSTREAM_CANDIDATE': 'pma_gap_memory_v0',
                     'GA_PMA_UPSTREAM_ENABLED': '1',
                     'GA_STATEFUL_MEMORY_ENABLED': '1',
                     'GA_EXPERIMENT_TASK_TURNS': '12'}
        with patch.dict(os.environ, inherited):
            with method_environment(resolve('pma-gap-evidence')):
                self.assertNotIn('GA_PMA_UPSTREAM_CANDIDATE', os.environ)
                self.assertNotIn('GA_EXPERIMENT_TASK_TURNS', os.environ)
                self.assertEqual(os.environ['GA_PMA_UPSTREAM_ENABLED'], '0')
                self.assertEqual(os.environ['GA_STATEFUL_MEMORY_ENABLED'], '0')
            self.assertEqual(os.environ['GA_PMA_UPSTREAM_CANDIDATE'], 'pma_gap_memory_v0')

    def test_bridge_allows_explicit_uncapped_candidate_only(self):
        path = Path(__file__).resolve().parents[1] / 'GenericAgent-main/pma_upstream_bridge.py'
        spec = importlib.util.spec_from_file_location('evidence_test_bridge', path)
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        with tempfile.TemporaryDirectory() as tmp:
            env = {'GA_BENCH_RUN_ID': 'fixture', 'GA_BENCH_TASK_ID': 'fixture',
                   'GA_PMA_UPSTREAM_REQUESTS': tmp, 'GA_PMA_UPSTREAM_RESPONSES': tmp,
                   'GA_PMA_UPSTREAM_DEADLINE_EPOCH': 'uncapped',
                   'GA_PMA_UPSTREAM_CANDIDATE': 'pma_gap_evidence_v1'}
            with patch.dict(os.environ, env, clear=True):
                with patch.object(bridge.UpstreamPMAClient, 'exchange') as exchange:
                    client = bridge.UpstreamPMAClient.from_environment('task')
                    self.assertIsNone(client.deadline)
                    exchange.assert_called_once_with('task_start', initial_user_content='task')
                os.environ['GA_PMA_UPSTREAM_CANDIDATE'] = 'U'
                with self.assertRaises(bridge.PMABridgeError):
                    bridge.UpstreamPMAClient.from_environment('task')

    def test_fake_provider_cites_the_actual_rendered_source(self):
        stage = Path(__file__).resolve().parents[1] / DRIVER.replace('.', '/')
        paths = [str(stage), str(stage / 'vendor/pma_89e5c0d/src'),
                 str(stage / 'vendor/pma_89e5c0d/external/harbor/src')]
        with patch.object(sys, 'path', paths + sys.path), patch.dict(
                os.environ, {'LITELLM_LOCAL_MODEL_COST_MAP': 'True'}):
            worker = importlib.import_module('worker_main')
            evidence = importlib.import_module('gap_evidence')
            importlib.import_module('evidence_gap_store')
        registry = evidence.SourceRegistry('fixture-only')
        text = 'The synthetic task asks for a result.'
        _, row = evidence.register_public_source(registry, event_id='actual-event',
            role='task_instruction', text=text, order=0, field_path='/initial_user_content',
            record_digest=evidence.sha256(text), record_digest_kind='field_text')
        parts = evidence.render_source_blocks([
            evidence.RenderBlock(registry.snapshot(row.source_id))], cycle_id='fixture-cycle')
        args = worker.fake_evidence_gap_arguments(SimpleNamespace(_parts=parts), parts.text)
        refs = evidence.bind_evidence(args['evidence'], parts.catalog)
        self.assertEqual(refs[0].source_id, row.source_id)
        self.assertEqual(args['evidence'][0]['quote'], text)
        with self.assertRaisesRegex(RuntimeError, 'no bound P1'):
            worker.fake_evidence_gap_arguments(SimpleNamespace(_parts=parts), 'different')

    def test_certification_requires_real_committed_gap_evidence(self):
        certification = importlib.import_module(DRIVER + '.single_run_certification')
        # Run the fixture-helper test first to load the real dependency stack.
        self.test_fake_provider_cites_the_actual_rendered_source()
        evidence = importlib.import_module('gap_evidence')
        store = importlib.import_module('evidence_gap_store')
        registry = evidence.SourceRegistry('certification-test')
        text = 'The fixture needs a checked result.'
        _, row = evidence.register_public_source(registry, event_id='source-event',
            role='task_instruction', text=text, order=0, field_path='/initial',
            record_digest=evidence.sha256(text), record_digest_kind='field_text')
        parts = evidence.render_source_blocks([
            evidence.RenderBlock(registry.snapshot(row.source_id))], cycle_id='cert-cycle')
        memory = store.EvidenceGapMemory()
        memory.retain_manifest(parts)
        refs = evidence.bind_evidence([{'source': row.handle, 'quote': text}], parts.catalog)
        memory.apply_bound_write('gap', 'Check the result.', refs, cycle_id='cert-cycle', op_index=0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'memory.json'
            import json
            path.write_text(json.dumps(memory.to_dict()))
            certification.require_bound_gap_memory(path)
            with patch.object(store, '__file__', '/foreign/evidence_gap_store.py'):
                with self.assertRaisesRegex(RuntimeError, 'foreign source'):
                    certification.require_bound_gap_memory(path)
            bad = memory.to_dict()
            bad['gap_evidence']['blobs'][evidence.sha256(text)] = 'forged source'
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                certification.require_bound_gap_memory(path)
            path.write_text(json.dumps(store.EvidenceGapMemory().to_dict()))
            with self.assertRaisesRegex(RuntimeError, 'no committed bound gap'):
                certification.require_bound_gap_memory(path)

    def test_evidence_source_identity_is_separate_and_complete(self):
        certification = importlib.import_module(DRIVER + '.single_run_certification')
        added = set(certification.EVIDENCE_GAP_SOURCE_FILES) - set(certification.GAP_SOURCE_FILES)
        prefix = DRIVER.replace('.', '/') + '/'
        expected = {
            'gap_evidence.py', 'evidence_gap_store.py', 'evidence_gap_agent.py',
            'evidence_gap_context.py', 'source_memory.py', 'evidence_requirements.txt',
            'aligned_evidence_gap_agent.py', 'aligned_evidence_gap_store.py',
            'gap_evidence_alignment.py', 'vendor/langextract_3a68580/__init__.py',
            'latest_evidence_gap_agent.py', 'latest_evidence_gap_store.py',
            'graded_evidence_alignment.py', 'vendor/langextract_3a68580/fuzzy.py',
            'fuzzy_candidate_windows.py', 'vendor/langextract_3a68580/chunking.py',
            'vendor/langextract_3a68580/alignment.py',
            'vendor/langextract_3a68580/tokenizer.py',
            'vendor/langextract_3a68580/requirements.txt',
        }
        self.assertEqual(added, {prefix + name for name in expected})
        checkout = Path(__file__).resolve().parents[1]
        def hash_working_bytes(root, name):
            self.assertEqual(root, checkout)
            return hashlib.sha256((root / name).read_bytes()).hexdigest()
        # Exercise identity dispatch with actual current bytes, not a constant.
        # This is source coverage only, not committed-source certification.
        with patch.object(certification, '_committed_source_sha',
                          side_effect=hash_working_bytes) as source_hash:
            old = certification.source_identity(checkout, gap=True)
            new = certification.source_identity(checkout, evidence_gap=True)
        self.assertEqual(set(new) - set(old), added)
        self.assertEqual({name for root, name in (call.args for call in source_hash.call_args_list)},
                         set(certification.EVIDENCE_GAP_SOURCE_FILES))
        for name in added:
            self.assertEqual(new[name], hashlib.sha256((checkout / name).read_bytes()).hexdigest())



if __name__ == '__main__':
    unittest.main()
