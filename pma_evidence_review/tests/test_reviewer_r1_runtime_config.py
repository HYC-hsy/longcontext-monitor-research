import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from pma_evidence_review import reviewer_r1_compare as compare


class RuntimeConfigTests(unittest.TestCase):
    def test_whitelist_and_write_precedes_first_request(self):
        private = {'max_tokens': 4096, 'thinking_type': 'adaptive',
                   'read_timeout': 120, 'apikey': 'DO_NOT_RECORD',
                   'apibase': 'https://private.example/key'}

        class Client:
            _model_name = 'anthropic/claude-opus-4-8'
            _temperature = 0.3
            _reasoning_effort = 'high'

            def __init__(self):
                memory_profile = private

                async def profiled_call(*, prompt, system, tools=None):
                    return memory_profile['max_tokens']

                self.call = profiled_call

        repo = Path(__file__).resolve().parents[2]
        client = Client()
        for arm in compare.ARMS:
            frozen = compare.plan(arm)
            value = compare.runtime_config(repo, frozen, client)
            self.assertEqual(value['arm'], arm)
            self.assertEqual(value['model_id'], 'anthropic/claude-opus-4-8')
            self.assertEqual(value['generation_parameters']['max_tokens'], 4096)
            self.assertEqual(value['generation_parameters']['top_p'], 'default/unknown')
            self.assertEqual(len(value['audit_request_sha256']), 22)
            self.assertNotIn('DO_NOT_RECORD', json.dumps(value))
            self.assertNotIn('private.example', json.dumps(value))

        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'run'

            async def check_before_request(frozen, transport):
                config = json.loads((output / 'run-config.json').read_text(encoding='utf-8'))
                self.assertEqual(config['plan_sha256'], frozen['plan_sha256'])
                return []

            argv = ['reviewer_r1_compare', 'run-profile', '--arm', 'v4-reviewer-r1',
                    '--repo', str(repo), '--profile', 'mock-only', '--out', str(output),
                    '--execute-authorized-real-model']
            with patch.object(sys, 'argv', argv), \
                 patch.object(compare, 'load_profile_client', return_value=client), \
                 patch.object(compare, 'CapturedTransport'), \
                 patch.object(compare, 'run', side_effect=check_before_request):
                compare.main()
            self.assertTrue((output / 'run-config.json').is_file())
            self.assertEqual(json.loads((output / 'results.json').read_text(encoding='utf-8'))['results'], [])


if __name__ == '__main__':
    unittest.main()
