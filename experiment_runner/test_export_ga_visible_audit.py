"""Small source/response boundary checks for the read-only GA exporter."""

import json
import tempfile
import unittest
from pathlib import Path

from experiment_runner.export_ga_visible_audit import export


class ExportGAVisibleAuditTest(unittest.TestCase):
    def test_complete_turn_and_hidden_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'run'
            archive = root / 'archive'
            agent = root / 'jobs' / 'j' / 't' / 'agent'
            verifier = agent.parent / 'verifier'
            archive.mkdir(parents=True)
            agent.mkdir(parents=True)
            verifier.mkdir()
            live = {'run_id': 'pma-test', 'condition': 'A',
                    'research_candidate': 'U', 'zero_model_fixture_only': False,
                    'native_result': {'status': 'native_recorded',
                                      'rewards': {'reward': 1.0}}}
            (archive / 'live_result.json').write_text(json.dumps(live))
            (agent / 'task_terminal.json').write_text('{"result":"done"}')
            (verifier / 'ctrf.json').write_text('{"results":{"summary":{"tests":1,"passed":1}}}')
            def event(kind, n, payload):
                return {'run_id': 'pma-test', 'event_type': kind,
                        'event_id': f'e{n}', 'llm_call_id': 'c1', 'payload': payload}
            events = [event('provider_request_ready', 1, {
                'content_availability': 'complete', 'sha256': 'request-hash',
                'content': {'messages': [{'content': [
                    {'type': 'thinking', 'thinking': 'SECRET_THOUGHT'},
                    {'type': 'text', 'text': 'visible question'}]}]}}),
                event('provider_response_content', 2, {'parsed_visible_blocks': [
                    {'type': 'text', 'text': 'visible answer'}]}),
                event('provider_response', 3, {'outcome': 'success'}),
                event('action_selected', 4, {'tool_call_ids': []})]
            (agent / 'research_events.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in events))
            counts = export(root, Path(tmp) / 'public', 'pma-test', [])
            self.assertEqual(counts['complete_visible_responses'], 1)
            public = (Path(tmp) / 'public' / 'task_turns.jsonl').read_text()
            self.assertIn('visible question', public)
            self.assertIn('visible answer', public)
            self.assertNotIn('SECRET_THOUGHT', public)


if __name__ == '__main__':
    unittest.main()
