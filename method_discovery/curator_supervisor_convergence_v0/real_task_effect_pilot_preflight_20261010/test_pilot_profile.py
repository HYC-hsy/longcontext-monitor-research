"""No-provider check of the exact Supervisor configuration transformation."""

import unittest

from .pilot_profile import (PILOT_OVERRIDES, public_profile_identity,
                            resolved_supervisor_profile)


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
        self.assertIs(public['incomplete_stream_recovery_v1'], True)

    def test_resolved_supervisor_client_opt_in_does_not_change_generic_default(self):
        from monitor_agent_core.provider import MonitorProviderClient

        base = {'model': 'claude-opus-4-8', 'max_tokens': 8192,
                'thinking_type': 'adaptive', 'reasoning_effort': 'high',
                'apikey': 'offline-secret', 'apibase': 'https://offline.invalid'}
        resolved = resolved_supervisor_profile(base)
        pilot = MonitorProviderClient('claude_monitor_opus48', resolved)
        generic = MonitorProviderClient('claude_monitor_opus48', base)
        self.assertIs(pilot.config['incomplete_stream_recovery_v1'], True)
        self.assertEqual(pilot.max_retries, 0)
        self.assertNotIn('incomplete_stream_recovery_v1', generic.config)

    def test_narrow_variant_is_explicit_and_publicly_identified(self):
        from monitor_agent_core.provider import MonitorProviderClient
        from monitor_agent_core.agent import MonitorAgent
        from monitor_agent_core.workspace import MonitorWorkspace
        import tempfile
        from pathlib import Path

        base = {'model': 'claude-opus-4-8', 'max_tokens': 8192,
                'thinking_type': 'adaptive', 'reasoning_effort': 'high',
                'apikey': 'offline-secret', 'apibase': 'https://offline.invalid'}
        resolved = resolved_supervisor_profile(base, variant='narrow_v1')
        public = public_profile_identity(resolved)
        self.assertIs(public['monitor_narrow_supervisor_v1'], True)
        self.assertIs(public['monitor_adaptive_supervisory_environment'], True)
        for key in ('monitor_contrastive_release_state', 'monitor_receding_horizon_release',
                    'monitor_root_epistemic_reestimation'):
            self.assertIs(public[key], False)
        self.assertEqual(public['monitor_history_projection'], 'off')
        client = MonitorProviderClient('claude_monitor_opus48', resolved)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / 'evidence'
            evidence.mkdir()
            (evidence / 'original_task.txt').write_text('Public task.', encoding='utf-8')
            monitor = MonitorAgent(client, MonitorWorkspace(evidence, root / 'private'))
            self.assertTrue(monitor.narrow_supervisor_v1)
            self.assertTrue(monitor.ase_v0)
            self.assertIsNone(monitor.crs)
        with self.assertRaisesRegex(ValueError, 'Incompatible'):
            resolved_supervisor_profile({**base, 'monitor_contrastive_release_state': True},
                                        variant='narrow_v1')


if __name__ == '__main__':
    unittest.main()
