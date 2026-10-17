"""No-network checks of the real Phase-2 screen route and one-use guard."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import litellm

import decision_phase2_screen as screen
import decision_phase2_archive as archive


PROFILE = Path('E:/LongContext/monitor_config/models.local.json')


class DecisionPhase2LiveTests(unittest.TestCase):
    def fixture(self, root: Path):
        manifest, auth, output = root / 'manifest.json', root / 'auth.json', root / 'out'
        identity = {'commit': 'fake-test-only', 'files': {'screen': 'fake-test-only'}}
        patcher = patch.object(screen, 'code_identity', return_value=identity)
        patcher.start()
        self.addCleanup(patcher.stop)
        screen.freeze(manifest, output, PROFILE)
        screen.authorize(manifest, auth, PROFILE, 'temporary forced-fake test')
        return manifest, auth, output

    @staticmethod
    def fake_response(content='<no_intervention/>'):
        return litellm.ModelResponse(model='claude-opus-4-8', choices=[{
            'message': {'content': content}, 'finish_reason': 'stop'}],
            usage={'prompt_tokens': 10, 'completion_tokens': 3})

    def test_profiled_actual_route_and_eighteen_ordered_fake_requests(self):
        with TemporaryDirectory() as temp:
            manifest, auth, output = self.fixture(Path(temp))
            sends = []

            async def lower(**kwargs):
                number = len(sends) + 1
                variant = ('U', 'V1', 'D1')[(number - 1) % 3]
                self.assertTrue((output / f'{number:02d}-{variant.lower()}' /
                                 'requests.jsonl').is_file())
                sends.append(kwargs)
                return self.fake_response()

            rows = asyncio.run(screen.run_authorized(manifest, auth, PROFILE,
                                                     fake_lower=lower))
            self.assertEqual(len(rows), 18)
            self.assertEqual(len(sends), 18)
            self.assertEqual([r['variant'] for r in rows], ['U', 'V1', 'D1'] * 6)
            self.assertEqual([r['observable_litellm_calls'] for r in rows], [1] * 18)
            self.assertFalse(auth.exists())
            self.assertEqual(len(list(output.glob('*/requests.jsonl'))), 18)
            self.assertTrue(all(row['status'] == 'completed' for row in rows))
            self.assertTrue(all(row['output_class'] == 'explicit_no_intervention'
                                for row in rows))
            for sent in sends:
                self.assertEqual(sent['model'], 'anthropic/claude-opus-4-8')
                self.assertEqual(sent['thinking'], {'type': 'adaptive'})
                self.assertEqual(sent['timeout'], 300)
                self.assertNotIn('tools', sent)
            for index in range(0, 18, 3):
                def text_content(content):
                    if isinstance(content, str):
                        return content
                    return ''.join(part['text'] for part in content)

                systems = [text_content(sends[index + j]['messages'][0]['content'])
                           for j in range(3)]
                prompts = [text_content(sends[index + j]['messages'][-1]['content'])
                           for j in range(3)]
                self.assertEqual(len(set(systems)), 3)
                self.assertEqual(len(set(prompts)), 3)
                archived = screen.read_case(rows[index]['arm'], rows[index]['pma_step'])['prompt']
                self.assertEqual(systems, [screen.PHASE2_SYSTEM,
                    screen.phase2_system('V1'), screen.phase2_system('D1')])
                self.assertEqual(prompts, [archived,
                    screen.phase2_prompt(archived, 'V1'),
                    screen.phase2_prompt(archived, 'D1')])
            self.assertFalse(any(output.glob('*/bank_states.jsonl')))
            public = Path(temp) / 'public'
            summary = archive.archive(output, manifest, public)
            self.assertEqual(summary['completed'], 18)
            self.assertEqual(len(list(public.glob('*/request.json'))), 18)
            self.assertTrue((public / 'raw_trajectories_public.zip').is_file())
            self.assertNotIn('api_key', (public / 'AUDIT.txt').read_text(encoding='utf-8'))

    def test_binding_mismatches_never_send(self):
        with TemporaryDirectory() as temp:
            manifest, auth, output = self.fixture(Path(temp))
            sends = []

            async def forbidden(**kwargs):
                sends.append(kwargs)
                raise AssertionError('network send forbidden')

            original = manifest.read_bytes()
            changed = json.loads(original)
            changed['planned_order'][0]['request_system_sha256'] = '0' * 64
            manifest.write_text(json.dumps(changed), encoding='utf-8')
            with self.assertRaises(PermissionError):
                asyncio.run(screen.run_authorized(manifest, auth, PROFILE,
                                                  fake_lower=forbidden))
            manifest.write_bytes(original)
            original_auth = auth.read_bytes()
            changed_auth = json.loads(original_auth)
            changed_auth['profile_sha256'] = '0' * 64
            auth.write_text(json.dumps(changed_auth), encoding='utf-8')
            with self.assertRaises(PermissionError):
                asyncio.run(screen.run_authorized(manifest, auth, PROFILE,
                                                  fake_lower=forbidden))
            auth.write_bytes(original_auth)
            with patch.object(screen, 'code_identity', return_value={'commit': 'drift'}):
                with self.assertRaises(PermissionError):
                    asyncio.run(screen.run_authorized(manifest, auth, PROFILE,
                                                      fake_lower=forbidden))
            altered = Path(temp) / 'changed-profile.json'
            altered.write_bytes(PROFILE.read_bytes() + b' ')
            with self.assertRaises(PermissionError):
                asyncio.run(screen.run_authorized(manifest, auth, altered,
                                                  fake_lower=forbidden))
            original_case = screen.read_case

            def changed_case(arm, step):
                row = original_case(arm, step)
                return {**row, 'prompt': row['prompt'] + ' tampered'}

            with patch.object(screen, 'read_case', side_effect=changed_case):
                with self.assertRaises(PermissionError):
                    asyncio.run(screen.run_authorized(manifest, auth, PROFILE,
                                                      fake_lower=forbidden))
            self.assertEqual(sends, [])
            self.assertFalse(output.exists())

    def test_final_provider_failure_stops_remaining_requests_without_outer_retry(self):
        with TemporaryDirectory() as temp:
            manifest, auth, output = self.fixture(Path(temp))
            sends = []

            async def failing(**kwargs):
                sends.append(kwargs)
                raise RuntimeError('scripted provider unavailable')

            rows = asyncio.run(screen.run_authorized(manifest, auth, PROFILE,
                                                     fake_lower=failing))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['status'], 'transport_final_failure')
            self.assertEqual(rows[0]['logical_requests'], 1)
            self.assertEqual(len(sends), 3)  # original LiteLLM retry, no outer replay
            self.assertFalse((output / '02-v1').exists())
            self.assertFalse(auth.exists())
            self.assertTrue((output / '01-u/requests.jsonl').exists())
            self.assertTrue((output / '01-u/result.json').exists())
            states = json.loads((output / 'status_table.json').read_text(encoding='utf-8'))['rows']
            self.assertEqual(states[0]['status'], 'transport_final_failure')
            self.assertEqual([row['status'] for row in states[1:]],
                             ['confirmed_not_started'] * 17)

    def test_accepted_response_capture_failure_is_not_resent(self):
        with TemporaryDirectory() as temp:
            manifest, auth, output = self.fixture(Path(temp))
            sends = []
            original_append = screen.append_json

            async def lower(**kwargs):
                sends.append(kwargs)
                return self.fake_response('<context_for_action>Check the result.</context_for_action>')

            def broken(path, row):
                if (path.name == 'provider_attempts_private.jsonl' and
                        row.get('event') == 'response_returned'):
                    raise screen.PMAAuditIntegrityError('synthetic accepted-capture failure')
                return original_append(path, row)

            with patch.object(screen, 'append_json', side_effect=broken):
                rows = asyncio.run(screen.run_authorized(manifest, auth, PROFILE,
                                                         fake_lower=lower))
            self.assertEqual(len(sends), 1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['status'], 'capture_integrity_failure')
            self.assertFalse((output / '02-v1').exists())
            self.assertFalse(auth.exists())

    def test_parser_projection_does_not_change_upstream_decision(self):
        cases = (
            ('<context_for_action>note</context_for_action>', 'context_tag_reminder'),
            ('<no_intervention/>', 'explicit_no_intervention'),
            ('<no_intervention />', 'explicit_no_intervention'),
            ('<no_intervention/> because', 'no_intervention_with_explanation'),
            ('<context_for_action>note</context_for_action><no_intervention/>',
             'mixed_markers'),
            ('', 'empty_response'), ('plain text', 'missing_marker'))
        for raw, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(screen.classify_output(raw, None), expected)

    def test_public_projection_excludes_thinking_and_secret_sentinels(self):
        cleaned, note = archive.safe_content('<think>PRIVATE_SENTINEL</think>visible')
        self.assertEqual(cleaned, '[thinking omitted]visible')
        self.assertEqual(note['status'], 'thinking_removed')
        cleaned, note = archive.safe_content('<think>PRIVATE_SENTINEL')
        self.assertIsNone(cleaned)
        self.assertEqual(note['status'], 'excluded_unclosed_thinking')
        cleaned, note = archive.safe_content('Bearer abcdefghijklmnop')
        self.assertIsNone(cleaned)
        self.assertEqual(note['status'], 'excluded_sensitive_pattern')


if __name__ == '__main__':
    unittest.main()
