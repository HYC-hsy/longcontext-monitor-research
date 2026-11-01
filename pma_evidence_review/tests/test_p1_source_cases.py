"""Frozen inputs and scripted lifecycle only; no semantic expected-answer checks."""
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

from pma_evidence_review.tests.test_bank_display import ROOT
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.tools.run_p1_source_case import run_case

CASES=ROOT/'pma_evidence_review/p1_source_read_delivery/cases'


class FrozenP1CaseTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_six_pre_model_cases_exact_hashes_and_explicit_origin(self):
        index=json.loads((CASES/'INDEX.json').read_text())
        self.assertEqual(index['status'],'frozen_before_real_calls')
        self.assertEqual(index['real_calls'],0);self.assertEqual(len(index['cases']),6)
        self.assertEqual(sum(x['kind']=='manual_control' for x in index['cases']),2)
        for row in index['cases']:
            path=CASES/row['file'];raw=path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
            case=json.loads(raw)
            self.assertTrue(case['observation_dimensions'])
            self.assertNotIn('expected_answer',case)
            self.assertLessEqual(len(case['entries']),8)
            self.assertEqual(len({w['window_id'] for w in case['source_windows']}),len(case['source_windows']))
            if row['kind']=='public_visible_reconstruction':
                self.assertIn('NOT an original production manifest',case['source_manifest']['transformation'])
                for window in case['source_windows']:
                    self.assertLess(window['historical_cycle_step'],case['step_count'])
                self.assertEqual([e['event_id'] for e in case['entries']],case['source_manifest']['accepted_event_ids'])

    def test_all_six_scripted_noops_make_only_one_p1_request_keep_bank_and_hide_dimensions(self):
        index=json.loads((CASES/'INDEX.json').read_text())
        for row in index['cases']:
            with self.subTest(case=row['file']),tempfile.TemporaryDirectory() as tmp:
                case=json.loads((CASES/row['file']).read_text());requests=[]
                case['observation_dimensions']=['WITHHELD_DIMENSION_SENTINEL']
                async def noop(**kw):
                    requests.append(kw)
                    return NS(content='',tool_calls=[])
                result=asyncio.run(run_case(case,Path(tmp),NS(call=noop)))
                self.assertEqual(result['status'],'completed')
                self.assertEqual(len(requests),1);self.assertEqual(result['operations'],[])
                self.assertEqual(result['reads_used'],0)
                self.assertNotIn('WITHHELD_DIMENSION_SENTINEL',requests[0]['prompt'])
                self.assertEqual(json.loads((Path(tmp)/'bank_after.json').read_text()),case['initial_bank'])
                config=json.loads((Path(tmp)/'run_config.json').read_text())
                self.assertFalse(config['native_messages_tool_roundtrip'])
                self.assertEqual(config['continuation_limit'],1)
                self.assertEqual(config['read_limit'],2)
                self.assertFalse(config['p2_enabled'])
