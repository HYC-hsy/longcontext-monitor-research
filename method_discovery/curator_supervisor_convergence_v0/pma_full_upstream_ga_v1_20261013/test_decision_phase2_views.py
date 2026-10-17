"""Offline checks of the archived D1 input-source diagnostic."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import litellm

import decision_phase2_screen as screen
from decision_phase2_views import PLACEHOLDER, project
import decision_phase2_archive as archive


PROFILE = Path('E:/LongContext/monitor_config/models.local.json')
OLD = screen.HERE / 'decision_phase2_live18_20261017/public_run'


class InputViewTests(unittest.TestCase):
    def fixture(self, root):
        manifest, auth, output = root / 'manifest.json', root / 'auth.json', root / 'out'
        identity = {'commit': 'forced-fake-only', 'files': {'screen': 'forced-fake-only'}}
        mocked = patch.object(screen, 'code_identity', return_value=identity)
        mocked.start()
        self.addCleanup(mocked.stop)
        screen.freeze(manifest, output, PROFILE, input_views=True)
        screen.authorize(manifest, auth, PROFILE, 'isolated forced-fake diagnostic')
        return manifest, auth, output

    @staticmethod
    def response(content='<no_intervention/>'):
        return litellm.ModelResponse(model='claude-opus-4-8', choices=[{
            'message': {'content': content}, 'finish_reason': 'stop'}],
            usage={'prompt_tokens': 9, 'completion_tokens': 2})

    def test_six_exact_F_and_field_projection(self):
        self.assertEqual(len(screen.view_requests()), 54)
        total_steps = 0
        for case_index, (arm, step) in enumerate(screen.CASES):
            full = screen.phase2_prompt(screen.read_case(arm, step)['prompt'], 'D1')
            previous = json.loads((OLD / f'{case_index * 3 + 3:02d}-d1/request.json')
                                  .read_text(encoding='utf-8'))
            self.assertEqual(full, previous['prompt'])
            self.assertEqual(screen.phase2_system('D1'), previous['system'])
            f, f_id = project(full, 'F')
            eb, eb_id = project(full, 'EB')
            e, e_id = project(full, 'E')
            self.assertEqual(full, f)
            self.assertEqual(eb_id['step_count'], e_id['step_count'])
            total_steps += f_id['step_count']
            self.assertEqual(eb_id['bank_original_sha256'], f_id['bank_original_sha256'])
            self.assertEqual(eb.split('</memory_bank>', 1)[1],
                             e.split('</memory_bank>', 1)[1])
            self.assertIn(PLACEHOLDER, e)
            self.assertNotIn(PLACEHOLDER, eb)
            for step_id in eb_id['steps']:
                self.assertTrue(step_id['analysis']['removed'])
                self.assertTrue(step_id['output_content']['removed'])
                self.assertTrue(step_id['commands']['preserved'])
                self.assertTrue(step_id['tool_results']['preserved'])
                self.assertGreater(step_id['tool_results']['count'], 0)
            self.assertNotIn('Agent Analysis: ', eb)
            self.assertNotIn('"content": "\\n### [WORKING MEMORY]', eb)
        self.assertEqual(total_steps, 43)

    def test_invalid_projection_structure_and_view_refused(self):
        full = screen.phase2_prompt(screen.read_case('07', 235)['prompt'], 'D1')
        for changed in (full.replace('Commands Executed: ', 'Commands: ', 1),
                        full.replace('"tool_results":', '"other_results":', 1),
                        full.replace('[Step 228]', '[Step 228]\nunknown event', 1)):
            with self.assertRaises(ValueError):
                project(changed, 'EB')
        with self.assertRaises(ValueError):
            project(full, '')

    def test_profiled_fifty_four_sends_and_archive(self):
        with TemporaryDirectory() as temporary:
            manifest, auth, root = self.fixture(Path(temporary))
            expected = screen.view_requests()
            sends = []

            async def lower(**kwargs):
                number = len(sends) + 1
                row = expected[number - 1]
                slot = root / screen.slot_name(row, number, screen.VIEW_SCHEMA)
                self.assertTrue((slot / 'requests.jsonl').is_file())
                sends.append(kwargs)
                return self.response()

            results = asyncio.run(screen.run_authorized(manifest, auth, PROFILE,
                                                         fake_lower=lower))
            self.assertEqual(len(sends), 54)
            self.assertEqual(len(results), 54)
            self.assertFalse(auth.exists())
            self.assertTrue(all(row['status'] == 'completed' for row in results))
            self.assertEqual([row['input_view'] for row in results],
                             [row['input_view'] for row in expected])
            for number, row in enumerate(expected, 1):
                content = sends[number - 1]['messages'][-1]['content']
                actual = content if isinstance(content, str) else ''.join(
                    part['text'] for part in content)
                prompt, _, _ = screen.request_for(row)
                self.assertEqual(actual, prompt)
                self.assertEqual(sends[number - 1]['timeout'], 300)
            public = Path(temporary) / 'public'
            self.assertEqual(archive.archive(root, manifest, public)['completed'], 54)
            self.assertEqual(len(list(public.glob('*/request.json'))), 54)
            self.assertEqual(len(list(public.glob('*/projection_identity.json'))), 54)

    def test_first_final_failure_stops_and_partial_archive(self):
        with TemporaryDirectory() as temporary:
            manifest, auth, root = self.fixture(Path(temporary))
            attempts = []

            async def final_failure(**kwargs):
                attempts.append(kwargs)
                raise ConnectionError('synthetic final transport failure')

            rows = asyncio.run(screen.run_authorized(manifest, auth, PROFILE,
                                                     fake_lower=final_failure))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['status'], 'transport_final_failure')
            self.assertEqual(len(attempts), 3)  # original internal retry only
            status = json.loads((root / 'status_table.json').read_text(encoding='utf-8'))['rows']
            self.assertEqual(sum(r['status'] == 'confirmed_not_started' for r in status), 53)
            self.assertFalse(auth.exists())
            self.assertEqual(archive.archive(root, manifest, Path(temporary) / 'public')
                             ['confirmed_not_started'], 53)

    def test_authorization_and_order_tamper_zero_send(self):
        with TemporaryDirectory() as temporary:
            manifest, auth, root = self.fixture(Path(temporary))
            original = manifest.read_bytes()
            frozen = json.loads(original)
            frozen['planned_order'][0], frozen['planned_order'][1] = (
                frozen['planned_order'][1], frozen['planned_order'][0])
            manifest.write_text(json.dumps(frozen), encoding='utf-8')
            with self.assertRaises(PermissionError):
                asyncio.run(screen.run_authorized(manifest, auth, PROFILE))
            self.assertFalse(root.exists())
            manifest.write_bytes(original)
            with patch.object(screen, 'code_identity', return_value={'commit': 'wrong'}):
                with self.assertRaises(PermissionError):
                    asyncio.run(screen.run_authorized(manifest, auth, PROFILE))
            self.assertFalse(root.exists())
            for field, changed in (
                    ('run_id', 'case-07-235-r1-f'),
                    ('request_prompt_sha256', '0' * 64),
                    ('source_file_sha256', '0' * 64)):
                altered = json.loads(original)
                altered['planned_order'][1][field] = changed
                manifest.write_text(json.dumps(altered), encoding='utf-8')
                with self.assertRaises(PermissionError):
                    asyncio.run(screen.run_authorized(manifest, auth, PROFILE))
                self.assertFalse(root.exists())
            altered = json.loads(original)
            altered['output_root'] = str(Path(temporary).parent / 'escaped-output')
            manifest.write_text(json.dumps(altered), encoding='utf-8')
            with self.assertRaises(PermissionError):
                asyncio.run(screen.run_authorized(manifest, auth, PROFILE))
            manifest.write_bytes(original)
            wrong_profile = Path(temporary) / 'wrong-profile.json'
            wrong_profile.write_text('{}', encoding='utf-8')
            with self.assertRaises(PermissionError):
                screen.check_authorized(manifest, auth, wrong_profile)
            self.assertFalse(root.exists())
            root.mkdir()
            with self.assertRaises(PermissionError):
                screen.check_authorized(manifest, auth, PROFILE)


if __name__ == '__main__':
    unittest.main()
