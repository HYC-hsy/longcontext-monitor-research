"""The batch projection preserves every source row with explicit redactions."""

import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_gap_batch20_visible import (
    _one_json, _stream)
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_gap_visible_audit import (
    Sanitizer, sha)


class BatchVisibleProjectionTests(unittest.TestCase):
    def test_stream_keeps_all_rows_and_private_original_mapping(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'events.jsonl'
            original = [
                b'{"id":1,"content":"public action","thinking":"private"}\n',
                b'{"id":2,"content":"sk-abcdefghijklmnop","tool":"code_run"}\n',
            ]
            source.write_bytes(b''.join(original))
            target = root / 'events.jsonl.gz'
            info = _stream(source, target, root, Sanitizer([]))
            shown = [json.loads(row) for row in gzip.open(target, 'rb')]
            self.assertEqual([row['value']['id'] for row in shown], [1, 2])
            self.assertEqual(info['rows'], 2)
            self.assertEqual([row['original_sha256'] for row in info['row_map']],
                             [sha(item) for item in original])
            self.assertEqual(shown[0]['value']['thinking']['excluded'], 'hidden_reasoning')
            self.assertNotIn(b'sk-abcdefghijklmnop', target.read_bytes())
            self.assertIn('[REDACTED]', shown[1]['value']['content'])

    def test_object_projection_and_source_boundary(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'memory.json'
            source.write_text('{"gap":"still open","api_key":"secret"}', encoding='utf-8')
            target = root / 'memory.json.gz'
            info = _one_json(source, target, root, Sanitizer([]))
            value = json.loads(gzip.open(target, 'rb').read())['value']
            self.assertEqual(value['gap'], 'still open')
            self.assertEqual(value['api_key']['excluded'], 'private_metadata_or_config')
            self.assertEqual(info['rows'], 1)
            with TemporaryDirectory() as outside:
                other = Path(outside) / 'other.json'
                other.write_text('{}', encoding='utf-8')
                with self.assertRaises(ValueError):
                    _one_json(other, root / 'outside.json.gz', root, Sanitizer([]))


if __name__ == '__main__':
    unittest.main()
