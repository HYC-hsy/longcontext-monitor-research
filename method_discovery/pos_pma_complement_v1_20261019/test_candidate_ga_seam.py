"""GA stateful Task payload plus real isolated candidate worker, fake HTTP only."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
GA = ROOT / 'GenericAgent-main'
POS = ROOT / 'method_discovery/pos_upstream_ga_v1_20261017'
PMA = ROOT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d'
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(GA))
from agent_loop import StepOutcome, agent_runner_loop, exhaust
from ga import GenericAgentHandler
from llmcore import NativeClaudeSession, NativeToolClient


class Tests(unittest.TestCase):
    def test_actual_ga_stateful_http_and_worker(self):
        initial = {'goal_specification': 'Make service available.', 'entities': [],
            'states': [], 'relations': [], 'epistemic_gaps': [],
            'achievement_gaps': [{'target': 'service available',
                                  'reason': 'not yet observed'}],
            'frontier': {'gap_type': 'achievement', 'target': 'service available'}}
        delta = {'remove_state_ids': [], 'remove_relation_ids': [],
            'upsert_entities': [], 'upsert_states': [], 'upsert_relations': [],
            'epistemic_gaps': [], 'achievement_gaps': initial['achievement_gaps'],
            'frontier': initial['frontier']}
        replies = {'belief': [json.dumps(initial), json.dumps(delta)],
            'consistency': ['{"issues": []}', '{"issues": []}'],
            'progress': ['{"progress": 0, "score": 0.0, '
                         '"affected_record_ids": [], "reason": "unchanged"}'],
            'pma_phase1': [{'content': '', 'tool_calls': []}] * 2,
            'pma_phase2': [{'content': '<context_for_action>Maybe inspect the port.</context_for_action>'},
                           {'content': '<no_intervention/>'}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / 'pos_runtime'
            runtime.mkdir()
            for name in ('worker.py', 'episode.py', 'citation_fix.py'):
                shutil.copy2(POS / name, runtime / name)
            for name in ('candidate.py', 'memory_adapter.py'):
                shutil.copy2(HERE / name, runtime / name)
            shutil.copytree(POS / 'vendor', runtime / 'vendor',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            shutil.copytree(PMA / 'src', runtime / 'pma_vendor' / 'src',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            fixture = root / 'replies.json'
            fixture.write_text(json.dumps(replies), encoding='utf-8')
            env = {'GA_POS_ENABLED': '1', 'GA_POS_PMA_COMPLEMENT': '1',
                'GA_PMA_ENABLED': '0', 'GA_PMA_UPSTREAM_ENABLED': '0',
                'GA_MONITOR_ENABLED': '0', 'GA_M0_MONITOR_ENABLED': '0',
                'GA_POS_TRANSPORT': 'fake',
                'GA_POS_WORKER_SCRIPT': str(runtime / 'worker.py'),
                'GA_POS_VENDOR_ROOT': str(runtime / 'vendor'),
                'GA_POS_EPISODE_MODULE': str(runtime / 'episode.py'),
                'GA_POS_ARCHIVE': str(root / 'events.jsonl'),
                'GA_POS_FAKE_REPLIES': str(fixture),
                'GA_BENCH_TASK_ID': 'synthetic', 'GA_LANG': 'en'}
            parent = SimpleNamespace(task_dir=tmp, extrakeyinfo=None,
                intervene=None, obligation_ledger=None,
                evidence_completion_kernel=None, research_condition=None,
                monitor_runtime=None, _turn_end_hooks={}, verbose=False)
            class Handler(GenericAgentHandler):
                def do_code_run(self, args, response):
                    if False: yield None
                    return StepOutcome({'stdout': 'ACTUAL_SYNTHETIC_TOOL_OUTPUT',
                        'exit_code': 0}, next_prompt='Synthetic tool complete')
            handler = Handler(parent, cwd=tmp)
            handler.history_info.append('ORDINARY_GA_HISTORY_CANARY')
            backend = NativeClaudeSession({'apibase': 'https://fixture.invalid',
                'apikey': 'SYNTHETIC-NO-ACCESS', 'model': 'claude-opus-4-8',
                'max_tokens': 64, 'max_retries': 0, 'stream': False})
            client = NativeToolClient(backend)
            parent.llmclient = client
            tools = json.loads((GA / 'assets/tools_schema.json').read_text(encoding='utf-8'))
            system = (GA / 'assets/sys_prompt_en.txt').read_text(encoding='utf-8')
            captured = []
            class HTTP:
                status_code = 200
                headers = {}
                def __init__(self, blocks): self.blocks = blocks
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def json(self): return {'content': self.blocks,
                    'usage': {'input_tokens': 1, 'output_tokens': 1}}
                def close(self): pass
            responses = [
                [{'type': 'tool_use', 'name': 'code_run', 'id': 'tool-1',
                  'input': {'type': 'python', 'script': 'print(1)'}}],
                [{'type': 'text', 'text': '<summary>Done.</summary>'}],
            ]
            def post(_url, **kwargs):
                captured.append(kwargs['json'])
                return HTTP(responses[len(captured) - 1])
            with patch.dict(os.environ, env), patch('llmcore.requests.post', side_effect=post):
                outcome = exhaust(agent_runner_loop(client, system, 'ORIGINAL_TASK',
                    handler, tools, max_turns=2, verbose=False))
            self.assertEqual(outcome['result'], 'CURRENT_TASK_DONE')
            self.assertEqual(len(captured), 2)
            first, second = [json.dumps(item, ensure_ascii=False) for item in captured]
            for payload in (first, second):
                self.assertIn('ORIGINAL_TASK', payload)
                self.assertIn('service available', payload)
                self.assertIn('code_run', payload)
            self.assertIn('"tool_use_id": "tool-1"', second)
            self.assertIn('Maybe inspect the port', first)
            self.assertNotIn('Maybe inspect the port', second)
            self.assertIn('ACTUAL_SYNTHETIC_TOOL_OUTPUT', second)
            self.assertEqual(len(backend.history), 4)
            rows = [json.loads(line) for line in (root / 'events.jsonl')
                    .read_text(encoding='utf-8').splitlines()]
            self.assertEqual(sum(row['event'] == 'candidate_pma_request' for row in rows), 4)
            self.assertTrue((root / 'events.result.json').is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
