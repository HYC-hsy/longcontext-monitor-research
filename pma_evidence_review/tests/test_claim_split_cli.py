"""Offline CLI parity and authorization boundaries; no real profile is opened."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pma_evidence_review import claim_split_cli as cli, claim_split as cs
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.tests.test_citation_review import synthetic
from pma_evidence_review.transport import FakeClient


class ClaimSplitCliTests(unittest.TestCase):
    def setUp(self): install_guard(self)

    def invoke(self, *args):
        with redirect_stdout(io.StringIO()): cli.main([str(a) for a in args])

    def test_actual_trace_direct_candidate_same_material_dynamic_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); outputs = []
            for strategy in (cli.ONE_SENTENCE, cs.STRATEGY):
                out = root / strategy
                self.invoke('fake', '--trace-fixture', 'sqlite_call_61', '--strategy', strategy, '--out', out)
                report = cli.read(out / 'report.json'); outputs.append(report)
                self.assertEqual(report['client_calls'], 2 if strategy == cs.STRATEGY else 1)
                self.assertEqual(report['results'][0]['verdict'], 'insufficient')
                self.assertTrue(report['fake']); self.assertFalse(report['memory_mutated'])
                captures = (out / 'requests.jsonl').read_text()
                self.assertNotIn('historical_baseline_response', captures)
                self.assertNotIn('reference_expectations', captures)
                self.invoke('export', '--trace-fixture', 'sqlite_call_61', '--strategy', strategy,
                            '--out', root / (strategy + '.json'))
                plan = cli.read(root / (strategy + '.json'))
                self.assertEqual(len(plan['initial_requests']), 1)
                self.assertEqual(plan['initial_requests'][0]['request'], report['results'][0]['request'])
            self.assertEqual(outputs[0]['input_sha256'], outputs[1]['input_sha256'])

    def test_existing_validated_packet_and_scripted_fake_same_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); packet = root / 'packet.json'; packet.write_text(json.dumps(synthetic()))
            rows, _ = cli.materials(packet); op = rows[0]['material']['original_operation']
            replies = [json.dumps({'op_index': op['op_index'], 'claims': [
                {'claim': op['content'], 'original_text': op['content']}]}),
                json.dumps({'results': [{'claim_index': 1, 'verdict': 'insufficient', 'evidence_ids': [],
                'original_fragment': op['content'], 'explanation': 'fixture'}],
                'decomposition_complete': True, 'coverage_original_fragment': '', 'coverage_explanation': 'fixture'})]
            responses = root / 'responses.json'; responses.write_text(json.dumps(replies))
            self.invoke('fake', '--input', packet, '--responses', responses, '--out', root / 'fake')
            client = FakeClient(replies)
            with patch.object(cli, 'load_profile_client', return_value=client):
                self.invoke('run-profile', '--input', packet, '--profile', 'absent',
                            '--execute-authorized-real-model', '--out', root / 'profile')
            captures = [json.loads(line)['request'] for line in (root / 'fake/requests.jsonl').read_text().splitlines()]
            self.assertEqual(client.calls, captures)
            with self.assertRaises(FileExistsError):
                self.invoke('fake', '--input', packet, '--out', root / 'fake')

    def test_real_authorization_absent_never_reads_input_or_profile(self):
        with patch.object(cli, 'materials') as material, patch.object(cli, 'load_profile_client') as loader:
            with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
                self.invoke('run-profile', '--input', 'absent', '--profile', 'absent', '--out', 'unused')
            material.assert_not_called(); loader.assert_not_called()

    def test_bad_or_extra_fake_responses_fail_and_leave_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for number, responses in enumerate((['{}'], ['{}', '{}', '{}'])):
                path = root / f'{number}.json'; path.write_text(json.dumps(responses))
                out = root / str(number)
                with self.assertRaises(SystemExit):
                    self.invoke('fake', '--trace-fixture', 'sqlite_call_19', '--responses', path, '--out', out)
                self.assertEqual(cli.read(out / 'report.json')['results'][0]['engineering_status'], 'parse_failure')
                self.assertTrue((out / 'responses.jsonl').exists())

    def test_hash_bound_trace_survives_actual_autocrlf_checkout(self):
        import os
        import subprocess
        source = Path(cli.__file__).parent / 'claim_split_delivery'
        env = {**os.environ, 'GIT_NO_LAZY_FETCH': '1', 'GIT_TERMINAL_PROMPT': '0'}
        def git(root, *args):
            return subprocess.check_output(['git', '-c', 'core.hooksPath=', '-c', 'commit.gpgsign=false',
                '-C', str(root), *args], env=env, stderr=subprocess.STDOUT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); origin = root / 'origin'; origin.mkdir(); git(origin, 'init')
            relative = Path('pma_evidence_review/claim_split_delivery')
            target = origin / relative; target.mkdir(parents=True)
            names = ('.gitattributes', 'TRACE_FIXTURES.json', 'PROVENANCE.json')
            for name in names: (target / name).write_bytes((source / name).read_bytes())
            (origin / 'control.txt').write_bytes(b'unprotected\n')
            git(origin, '-c', 'core.autocrlf=false', 'add', '.')
            git(origin, '-c', 'user.name=Offline Fixture', '-c', 'user.email=fixture@example.invalid',
                'commit', '-m', 'Trace byte fixture')
            checkout = root / 'checkout'
            git(root, 'clone', '--no-hardlinks', '--config', 'core.autocrlf=true', str(origin), str(checkout))
            self.assertEqual((checkout / 'control.txt').read_bytes(), b'unprotected\r\n')
            for name in names:
                self.assertEqual((checkout / relative / name).read_bytes(), (source / name).read_bytes())
            with patch.object(cli, '__file__', str(checkout / 'pma_evidence_review/claim_split_cli.py')):
                rows, _ = cli.materials(trace_fixture='sqlite_call_19')
                self.assertEqual(rows[0]['op_index'], 0)
            self.assertIn(b'text: unset', git(checkout, 'check-attr', 'text', '--',
                                            str(relative / 'TRACE_FIXTURES.json')))
