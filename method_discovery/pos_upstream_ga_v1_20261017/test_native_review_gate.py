"""Offline negative gates for the one historical native-unscored review."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from . import serial_live


class NativeReviewGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = ('POS_REVIEW_SCOPE', 'POS_REVIEW_CERT', 'POS_REVIEW_PROFILE',
                 'POS_REVIEW_CONTINUITY', 'POS_REVIEW_PATH')
        missing = [name for name in names if not os.environ.get(name)]
        if missing:
            raise RuntimeError('current prepared offline review fixtures missing: ' +
                               ','.join(missing))
        cls.scope, cls.cert, cls.profile, cls.continuity, cls.review = (
            Path(os.environ[name]) for name in names)

    def expected(self):
        return serial_live.native_unscored_review(
            self.scope, self.cert, self.profile, self.continuity)

    def test_exact_review_and_old_failed_status_preserved(self):
        expected = self.expected()
        actual = json.loads(self.review.read_text(encoding='utf-8'))
        self.assertEqual(actual, expected)
        self.assertEqual(actual['historical_status'], 'failed')
        self.assertEqual(actual['progress'], 'invalid_unscored_not_zero')
        self.assertEqual(actual['initial_audit'], 'completed_once')
        self.assertEqual(actual['update_audit'], 'completed_twice_repaired')

    def test_wrong_historical_probe_or_old_v1_v2_rejected(self):
        wrong = dict(serial_live.HISTORICAL_PROBE_HASHES)
        wrong['role_events.jsonl'] = '0' * 64
        with patch.object(serial_live, 'HISTORICAL_PROBE_HASHES', wrong):
            with self.assertRaisesRegex(RuntimeError, 'historical v3'):
                self.expected()
        old_v1 = serial_live.HISTORICAL_PROBE.parent.parent / 'raw_compat_v1'
        with patch.object(serial_live, 'HISTORICAL_PROBE', old_v1):
            with self.assertRaises(RuntimeError):
                self.expected()

    def test_wrong_code_or_profile_rejected(self):
        changed = serial_live.source_hashes()
        changed['method_discovery/pos_upstream_ga_v1_20261017/worker.py'] = '0' * 64
        with patch.object(serial_live, 'source_hashes', return_value=changed):
            with self.assertRaisesRegex(RuntimeError, 'current method/source'):
                self.expected()
        with tempfile.TemporaryDirectory() as tmp:
            wrong_profile = Path(tmp) / 'profile.txt'
            wrong_profile.write_text('not the private profile', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'current method/source'):
                serial_live.native_unscored_review(
                    self.scope, self.cert, wrong_profile, self.continuity)

    def test_unreviewed_and_tampered_review_never_authorize(self):
        args = SimpleNamespace(output=str(self.scope.parent),
            certification=str(self.cert), task_profile_file=str(self.profile),
            compatibility_result=None, compatibility_review=None,
            continuity_evidence=str(self.continuity))
        with self.assertRaisesRegex(RuntimeError, 'exactly one'):
            serial_live.run(args)
        self.assertFalse(any(self.scope.parent.rglob('authorization.json')))
        with tempfile.TemporaryDirectory() as tmp:
            tampered = json.loads(self.review.read_text(encoding='utf-8'))
            tampered['accepted_failure'] = 'all_failures_allowed'
            path = Path(tmp) / 'review.json'
            path.write_text(json.dumps(tampered), encoding='utf-8')
            args.compatibility_review = str(path)
            with self.assertRaisesRegex(RuntimeError, 'review identity'):
                serial_live.run(args)
            self.assertFalse(any(self.scope.parent.rglob('authorization.json')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
