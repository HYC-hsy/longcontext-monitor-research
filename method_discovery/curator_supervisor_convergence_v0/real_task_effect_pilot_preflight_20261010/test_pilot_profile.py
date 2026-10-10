"""No-provider check of the exact Supervisor configuration transformation."""

import unittest

from .pilot_profile import PILOT_OVERRIDES, public_profile_identity, resolved_supervisor_profile


class PilotProfileTests(unittest.TestCase):
    def test_only_explicit_authorized_fields_change_and_no_credential_is_reported(self):
        base = {'model': 'claude-opus-4-8', 'max_tokens': 8192,
                'thinking_type': 'adaptive', 'reasoning_effort': 'high',
                'temperature': 1, 'apikey': 'offline-secret',
                'apibase': 'https://offline.invalid', 'timeout': 30,
                'read_timeout': 300, 'max_retries': 8, 'verify': None,
                'other_deployed_field': 'unchanged'}
        result = resolved_supervisor_profile(base)
        self.assertEqual({k for k in result if base.get(k) != result[k]},
                         {k for k, value in PILOT_OVERRIDES.items() if base.get(k) != value})
        self.assertEqual(result['other_deployed_field'], 'unchanged')
        self.assertEqual(result['temperature'], 1)
        public = public_profile_identity(result)
        self.assertNotIn('apikey', public)
        self.assertNotIn('apibase', public)
        self.assertEqual(public['max_retries'], 0)
        self.assertEqual(public['monitor_history_projection'], 'root_records_v1')


if __name__ == '__main__':
    unittest.main()
