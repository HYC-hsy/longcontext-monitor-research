"""Post-stop capture accounting; no provider or Task execution."""
import json
from pathlib import Path
import tempfile
import unittest

from .provider_capture import inspect_provider_capture


class CaptureAccountingTests(unittest.TestCase):
    def test_zero_calls_is_distinct_from_missing_after_role_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            role = root/'events.jsonl'
            role.write_bytes(b'')
            zero = inspect_provider_capture(root,'run','task',profile_mode=True)
            self.assertEqual(zero['status'],'no_role_calls')
            self.assertEqual(zero['observable_attempts'],0)
            self.assertTrue(zero['capture_complete'])
            role.write_text(json.dumps({'event':'pos_role_request','role':'belief'})+'\n')
            missing = inspect_provider_capture(root,'run','task',profile_mode=True)
            self.assertEqual(missing['status'],'provider_file_missing_or_pre_send_failure')
            self.assertIsNone(missing['observable_attempts'])
            self.assertFalse(missing['capture_complete'])

    def test_partial_or_wrong_identity_never_looks_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'events.jsonl').write_text(
                json.dumps({'event':'pos_role_request','role':'belief'})+'\n')
            event = {'run_id':'run','task_id':'task','condition_id':'P',
                     'branch_id':'pos-role-belief','llm_call_id':'call',
                     'event_type':'provider_request_ready'}
            provider = root/'events.provider.jsonl'
            provider.write_text(json.dumps(event)+'\n')
            partial = inspect_provider_capture(root,'run','task',profile_mode=True)
            self.assertEqual(partial['status'],'provider_attempt_or_return_incomplete')
            self.assertEqual(partial['observable_attempts'],0)
            self.assertFalse(partial['capture_complete'])
            event['run_id']='other'
            provider.write_text(json.dumps(event)+'\n')
            mismatch = inspect_provider_capture(root,'run','task',profile_mode=True)
            self.assertEqual(mismatch['status'],'provider_identity_mismatch')


if __name__ == '__main__': unittest.main()
