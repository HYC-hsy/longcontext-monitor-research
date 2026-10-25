"""Frozen packet and existing archive identity regressions; no model requests."""
import asyncio
import copy
import gzip
import hashlib
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pma_evidence_review.inputs import (build, build_from_data, digest, load_indexed,
    review_input_identity, validate, visible_sources, D, SAMPLES)
from pma_evidence_review.review import extraction_request, review
from pma_evidence_review.transport import CapturedTransport, FakeClient
from pma_evidence_review.location import locate
from pma_evidence_review.tests.fixtures import bundle, packet, extraction, result

ROOT = Path(__file__).resolve().parents[2]


class IdentityTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden'))
        blocked = guard.start()
        self.addCleanup(guard.stop)
        self.addCleanup(lambda: self.assertEqual(blocked.call_count, 0))

    def test_sqlite_operation_and_deletion_mutations_rejected(self):
        original = build(ROOT, 'sqlite')
        for key in ('content', 'before'):
            p = copy.deepcopy(original)
            if key == 'before':
                p['operations'][1]['before']['content'] = 'FUTURE_SENTINEL'
            else:
                p['operations'][1]['content'] = 'FUTURE_SENTINEL'
            self.assertEqual(p['request_sha256'], original['request_sha256'])
            with self.assertRaises(ValueError):
                extraction_request(p)
        p = copy.deepcopy(original)
        p['operations'][1]['content'] = 'changed deletion target'
        p['operations'][1]['content_sha256'] = digest(p['operations'][1]['content'])
        p['review_input_sha256'] = review_input_identity(p)
        with self.assertRaisesRegex(ValueError, 'deletion_revision_mismatch'):
            validate(p)

    def test_new_write_material_has_new_full_input_identity(self):
        p = packet()
        old_hash, prompt_hash = p['review_input_sha256'], p['request_sha256']
        p['operations'][0]['content'] = 'Different proposed content.'
        p['operations'][0]['content_sha256'] = digest(p['operations'][0]['content'])
        with self.assertRaisesRegex(ValueError, 'review_input_hash_mismatch'):
            validate(p)
        p['review_input_sha256'] = review_input_identity(p)
        validate(p)
        self.assertNotEqual(old_hash, p['review_input_sha256'])
        self.assertEqual(prompt_hash, p['request_sha256'])
        # Re-sealing is a new candidate input, not proof of the old archive operation.

    def test_source_event_and_visibility_tampering(self):
        original = packet()
        for mutation in ('event', 'visibility'):
            p = copy.deepcopy(original)
            if mutation == 'event':
                sid = json.loads(p['manifest']['ordered_source_refs'][0])
                sid[2] = 'wrong_event'
                sid = json.dumps(sid, separators=(',', ':'))
                p['manifest']['ordered_source_refs'][0] = sid
                # Even recomputing visibility cannot rename the sealed prompt header.
                p['manifest']['visibility_refs'][0] = digest(json.dumps([
                    p['cycle_id'], p['request_sha256'], sid,
                    p['manifest']['visible_spans'][0]], separators=(',', ':')))
            else:
                p['manifest']['visibility_refs'][0] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'source_handle_mismatch|visibility_ref_mismatch'):
                visible_sources(p['maintenance_prompt'], p['manifest'])

    def test_public_gzip_and_decompressed_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp, 'sample.json.gz')
            raw = gzip.compress(b'{"value":{"text":"synthetic"}}')
            path.write_bytes(raw)
            entry = {'public': path.name, 'public_gzip_bytes': len(raw),
                'public_gzip_sha256': hashlib.sha256(raw).hexdigest(),
                'public_uncompressed_sha256': hashlib.sha256(gzip.decompress(raw)).hexdigest()}
            self.assertEqual(load_indexed(path, [entry]), {'text':'synthetic'})
            path.write_bytes(raw + b'x')
            with self.assertRaisesRegex(ValueError, 'public_gzip_hash'):
                load_indexed(path, [entry])
            path.write_bytes(raw)
            entry['public_uncompressed_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'public_uncompressed_hash'):
                load_indexed(path, [entry])

    def test_slot_index_hash(self):
        base = D / 'source_window_two_real_20261025'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            slot = root / base / SAMPLES['sqlite'][0]
            slot.mkdir(parents=True)
            (root / base / 'INDEX.json').write_bytes((ROOT / base / 'INDEX.json').read_bytes())
            (slot / 'INDEX.json').write_text('{"files":[]}')
            with self.assertRaisesRegex(ValueError, 'slot_index_hash'):
                build(root, 'sqlite')

    def test_same_cycle_update_update_delete_and_no_future(self):
        args = bundle()
        store = args[3]['gap_evidence']
        store['revisions']['old']['category'] = 'gap'
        store['revisions']['new']['category'] = 'gap'
        args[1]['steps'][0]['operations'][0]['action'] = 'save_gap'
        content = 'Second update in this cycle.'
        store['blobs'][digest(content)] = content
        store['revisions']['new2'] = dict(store['revisions']['new'], revision_id='new2',
            previous_revision_id='new', receipt_id='r2', content_sha256=digest(content))
        store['receipts']['r2'] = {'cycle_id':'c1', 'op_index':1}
        store['tombstones']['t2'] = {'cycle_id':'c1','op_index':2,'memory_id':'m1','revision_id':'new2'}
        args[1]['steps'][0]['operations'] += [
            {'action':'save_gap','memory_id':'m1','content':content,'success':True},
            {'action':'delete_gap','memory_id':'m1','content':None,'success':True}]
        args[2][0]['evidence_report']['operations'] += [
            {'index':1,'success':True,'revision_id':'new2','binding_status':'unbound'},
            {'index':2,'success':True}]
        p = build_from_data(*args, step=1, cycle_id='c1')
        self.assertEqual([o['before']['revision_id'] for o in p['operations']], ['old','new','new2'])
        self.assertEqual(p['operations'][2]['content'], content)
        store['revisions']['new2']['previous_revision_id'] = 'future'
        with self.assertRaisesRegex(ValueError, 'previous_revision_not_visible'):
            build_from_data(*args, step=1, cycle_id='c1')

    def test_core_consumes_packet_without_archive_adapter(self):
        p = packet()
        transport = CapturedTransport(FakeClient([extraction(), result()]), fake=True)
        with patch('pma_evidence_review.inputs.build', side_effect=AssertionError('no archive')), \
             patch('pma_evidence_review.inputs.load', side_effect=AssertionError('no bank')):
            report = asyncio.run(review(p, transport, locator=locate))
        self.assertEqual(report['review_input_sha256'], p['review_input_sha256'])
        self.assertEqual(report['results'][0]['memory_id'], p['operations'][0]['memory_id'])
