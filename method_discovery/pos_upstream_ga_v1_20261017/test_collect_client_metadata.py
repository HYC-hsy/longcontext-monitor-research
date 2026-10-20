"""Offline safety checks for the public native-SHARED evidence exporter."""
import json
import unittest

from .collect_native_shared import redact_client_metadata


class ClientMetadataTests(unittest.TestCase):
    def test_json_and_nested_jsonl_preserve_task_messages(self):
        payload = {'payload': {'content': {
            'metadata': {'user_id': '{"device_id":"PRIVATE_CLIENT_ID"}'},
            'messages': [{'role': 'user', 'content': 'Keep complete Task text'}],
            'tools': [{'name': 'synthetic_tool'}]}}}
        source = (json.dumps(payload) + '\n' + json.dumps({
            'nested': json.dumps(payload)} ) + '\n').encode()
        public, changes = redact_client_metadata(source)
        self.assertEqual(changes, 2)
        self.assertNotIn(b'PRIVATE_CLIENT_ID', public)
        self.assertIn(b'Keep complete Task text', public)
        self.assertIn(b'synthetic_tool', public)

    def test_malformed_metadata_fails_closed(self):
        with self.assertRaises(RuntimeError):
            redact_client_metadata(b'{"metadata":{"user_id":"private"}')


if __name__ == '__main__':
    unittest.main()
