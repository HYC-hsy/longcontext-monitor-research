"""A real isolated JSONL worker process with finite fake PoS/PMA transport."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
POS = ROOT / 'pos_upstream_ga_v1_20261017'
PMA = ROOT / 'curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d'
HERE = Path(__file__).resolve().parent


class WorkerTests(unittest.TestCase):
    def test_initial_consistency_transport_failure_is_not_swallowed(self):
        initial = {'goal_specification': 'Clean mug.', 'entities': [], 'states': [],
                   'relations': [], 'epistemic_gaps': [], 'achievement_gaps': [],
                   'frontier': None}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
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
            fixture.write_text(json.dumps({'belief': [json.dumps(initial)],
                'consistency': [{'raise': 'synthetic transport failure'}]}),
                encoding='utf-8')
            command = {'kind': 'reset', 'candidate': True, 'case_id': 'synthetic/mug',
                       'task': 'Clean mug.', 'observation': 'Mug dirty.', 'actions': []}
            process = subprocess.run([sys.executable, '-B', str(runtime / 'worker.py'),
                '--vendor', str(runtime / 'vendor'), '--episode-module', str(runtime / 'episode.py'),
                '--archive', str(root / 'events.jsonl'), '--mode', 'fake',
                '--fake-replies', str(fixture)], input=json.dumps(command) + '\n',
                text=True, encoding='utf-8', capture_output=True, timeout=15)
            outputs = [json.loads(line) for line in process.stdout.splitlines()]
            self.assertEqual(outputs[0]['status'], 'error')
            self.assertEqual(outputs[0]['error_type'], 'CandidateRoleTransportFailure')
            result = json.loads((root / 'events.result.json').read_text(encoding='utf-8'))
            # This error precedes the original manager's initial commit.
            # There is no committed state to invent as a partial snapshot.
            self.assertEqual(result['status'], 'missing')
            self.assertIsNone(result['result'])
            fixture.write_text(json.dumps({'belief': [json.dumps(initial)],
                'consistency': ['{"issues": []}'],
                'pma_phase1': [{'raise': 'synthetic PMA transport failure'}]}),
                encoding='utf-8')
            second_archive = root / 'after_commit.jsonl'
            process = subprocess.run([sys.executable, '-B', str(runtime / 'worker.py'),
                '--vendor', str(runtime / 'vendor'), '--episode-module', str(runtime / 'episode.py'),
                '--archive', str(second_archive), '--mode', 'fake',
                '--fake-replies', str(fixture)], input=json.dumps(command) + '\n',
                text=True, encoding='utf-8', capture_output=True, timeout=15)
            self.assertEqual(json.loads(process.stdout.splitlines()[0])['status'], 'error')
            committed = json.loads((root / 'after_commit.result.json').read_text(encoding='utf-8'))
            self.assertEqual(committed['status'], 'partial')
            self.assertEqual(committed['result']['pos']['belief_state']['goal']['specification'],
                             'Clean mug.')

    def test_packed_candidate_reset_update_finish(self):
        initial = {'goal_specification': 'Clean mug.', 'entities': [], 'states': [],
                   'relations': [], 'epistemic_gaps': [],
                   'achievement_gaps': [{'target': 'clean', 'reason': 'unverified'}],
                   'frontier': {'gap_type': 'achievement', 'target': 'clean'}}
        update = {'remove_state_ids': [], 'remove_relation_ids': [],
                  'upsert_entities': [], 'upsert_states': [], 'upsert_relations': [],
                  'epistemic_gaps': [], 'achievement_gaps': initial['achievement_gaps'],
                  'frontier': initial['frontier']}
        replies = {'belief': [json.dumps(initial), json.dumps(update)],
                   'consistency': ['{"issues": []}', '{"issues": []}'],
                   'progress': ['{"progress": 0, "score": 0.0, '
                                '"affected_record_ids": [], "reason": "no change"}'],
                   'pma_phase1': [{'content': '', 'tool_calls': []}] * 2,
                   'pma_phase2': [{'content': '<context_for_action>Check again</context_for_action>'},
                                  {'content': '<no_intervention/>'}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
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
            archive = root / 'events.jsonl'
            commands = [
                {'kind': 'reset', 'candidate': True, 'case_id': 'synthetic/mug',
                 'task': 'Clean mug.', 'observation': 'Mug dirty.', 'actions': []},
                {'kind': 'decision_panel', 'observation': 'Mug dirty.'},
            ]
            process = subprocess.Popen([sys.executable, '-B', str(runtime / 'worker.py'),
                '--vendor', str(runtime / 'vendor'), '--episode-module', str(runtime / 'episode.py'),
                '--archive', str(archive), '--mode', 'fake', '--fake-replies', str(fixture)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8')
            for command in commands:
                process.stdin.write(json.dumps(command) + '\n')
                process.stdin.flush()
            first = json.loads(process.stdout.readline())
            second = json.loads(process.stdout.readline())
            self.assertEqual(first['status'], 'ok')
            panel = second['result']
            self.assertIn('Check again', panel['panel'])
            tail = [
                {'kind': 'request_accepted', 'panel': panel, 'event_id': 'task-1'},
                {'kind': 'decision_completed', 'turn': 1, 'action_count': 1},
                {'kind': 'update', 'actor_attempt': 1, 'transition_id': 'joint-1',
                 'thought': 'inspect', 'action_batch': [{'id': 't1', 'name': 'inspect',
                   'arguments': {}, 'order': 0, 'status': 'executed'}],
                 'observation': 'Still dirty.'},
                {'kind': 'finish', 'reason': 'CURRENT_TASK_DONE',
                 'observation': 'Still dirty.'},
            ]
            for command in tail:
                process.stdin.write(json.dumps(command) + '\n')
                process.stdin.flush()
            process.stdin.close()
            output = [json.loads(line) for line in process.stdout]
            stderr = process.stderr.read()
            process.stdout.close()
            process.stderr.close()
            self.assertEqual(process.wait(timeout=15), 0, stderr)
            self.assertTrue(all(row['status'] == 'ok' for row in output), output)
            self.assertEqual(output[-1]['result']['status'], 'completed')
            self.assertTrue(archive.with_suffix('.result.json').is_file())
            events = [json.loads(line) for line in archive.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(sum(x.get('event') == 'pos_role_request' for x in events), 5)
            self.assertEqual(sum(x.get('event') == 'candidate_pma_request' for x in events), 4)


if __name__ == '__main__':
    unittest.main(verbosity=2)
