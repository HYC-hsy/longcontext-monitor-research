import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from evidence_gap_store import EvidenceGapMemory
from gap_store import GapMemory
from gap_evidence import (SourceRegistry, register_public_source, RenderBlock,
                          render_source_blocks, bind_evidence, sha256)
from memory_agent.memory.universal_memory import UniversalMemory


class EvidenceBankTests(unittest.TestCase):
    def parts(self, cycle='c1', text='public observation', registry=None):
        registry = registry or SourceRegistry('run')
        _, record = register_public_source(registry, event_id='event', role='tool_observation',
            text=text, order=1, field_path='output', record_digest=sha256('envelope'),
            record_digest_kind='accepted_public_envelope')
        parts = render_source_blocks([RenderBlock(registry.snapshot(record.source_id))], cycle_id=cycle)
        refs = bind_evidence([{'source': record.handle, 'quote': text}], parts.catalog)
        return parts, refs

    def write(self, bank, kind='knowledge', content='fact', cycle='c1'):
        draft = bank.fork_write_draft()
        parts, refs = self.parts(cycle)
        draft.retain_manifest(parts)
        result = draft.apply_bound_write(kind, content, refs, cycle_id=cycle, op_index=0)
        bank.publish(bank.prepare_publication(draft))
        return result

    def test_all_writers_and_status_truncation(self):
        bank = EvidenceGapMemory(max_status_length=3)
        for i, kind in enumerate(('knowledge', 'procedural', 'gap', 'status')):
            writer = 'update_status' if kind == 'status' else 'save_' + kind
            owner = GapMemory if kind == 'gap' else UniversalMemory
            original = getattr(owner, writer)
            called = []
            def spy(instance, content):
                called.append(instance)
                return original(instance, content)
            with patch.object(owner, writer, spy):
                key, revision = self.write(bank, kind, 'abcdef', str(i))
            self.assertEqual(len(called), 1)
            self.assertIsNot(called[0], bank)
            actual = bank.status if kind == 'status' else bank._content(key)[1]
            self.assertEqual(bank.revisions[revision].content_sha256, sha256(actual))
        self.assertEqual(bank.status, 'abc...')
        restored = EvidenceGapMemory.from_dict(json.loads(json.dumps(bank.to_dict())))
        self.assertEqual(restored.to_dict(), bank.to_dict())
        self.assertEqual(restored._max_status_length, 3)

    def test_equal_status_has_distinct_revisions_and_tamper_fails(self):
        bank = EvidenceGapMemory()
        _, first = self.write(bank, 'status', 'same', 'first')
        _, second = self.write(bank, 'status', 'same', 'second')
        self.assertNotEqual(first, second)
        self.assertEqual(bank.revisions[first].content_sha256, bank.revisions[second].content_sha256)
        data = bank.to_dict()
        visible = next(iter(data['gap_evidence']['visibility'].values()))
        visible['request_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            EvidenceGapMemory.from_dict(data)
        with self.assertRaises(ValueError):
            EvidenceGapMemory.from_dict({'gap_evidence': None})

    def test_shared_history_active_only_stage_and_rollback(self):
        bank = EvidenceGapMemory()
        self.write(bank)
        before = bank.to_dict()
        draft = bank.fork_write_draft()
        self.assertIs(draft.revisions, bank.revisions)
        self.assertIs(draft._knowledge[0], bank._knowledge[0])
        self.assertIsNot(draft._knowledge, bank._knowledge)
        self.assertIsNot(draft.active_revisions, bank.active_revisions)
        draft.delete_bound(bank.knowledge[0].id)
        with patch.object(draft, 'validate_bank', side_effect=ValueError('injected')):
            with self.assertRaises(ValueError):
                bank.prepare_publication(draft)
        self.assertEqual(before, bank.to_dict())
        self.assertEqual(bank.knowledge[0].access_count, 0)

    def test_publication_identity_and_stale_foreign_tokens(self):
        bank = EvidenceGapMemory()
        identity = id(bank)
        d1, d2 = bank.fork_write_draft(), bank.fork_write_draft()
        p1, p2 = bank.prepare_publication(d1), bank.prepare_publication(d2)
        with self.assertRaises(ValueError):
            EvidenceGapMemory().publish(p1)
        bank.publish(p1)
        self.assertEqual(id(bank), identity)
        with self.assertRaises(ValueError):
            bank.publish(p2)

    def test_deleted_parent_revision_remains_resolvable(self):
        bank = EvidenceGapMemory()
        parent = bank.save_knowledge('legacy old text')
        draft = bank.fork_write_draft()
        registry = SourceRegistry('memory-cycle')
        record = draft.memory_source(registry, parent)
        revision = record.parent_revision_id
        parts = render_source_blocks([RenderBlock(registry.snapshot(record.source_id))], cycle_id='derived')
        refs = bind_evidence([{'source': record.handle, 'quote': 'old text'}], parts.catalog)
        draft.retain_manifest(parts)
        draft.delete_bound(parent)
        child, _ = draft.apply_bound_write('gap', 'missing fact', refs, cycle_id='derived', op_index=1)
        bank.publish(bank.prepare_publication(draft))
        self.assertIsNone(bank.get(parent))
        self.assertIsNone(bank.revisions[revision].receipt_id)
        self.assertTrue(bank._content(child))
        self.assertEqual(EvidenceGapMemory.from_dict(bank.to_dict()).to_dict(), bank.to_dict())

    def test_retired_ids_cannot_be_reused_and_reset_preserves_history(self):
        bank = EvidenceGapMemory()
        key, _ = self.write(bank)
        bank.delete(key)
        with patch.object(UniversalMemory, '_generate_id', return_value=key):
            self.assertNotEqual(bank.save_knowledge('new'), key)
        gap = bank.save_gap('old gap')
        bank.delete_gap(gap)
        with patch('gap_store.shortuuid.uuid', return_value=gap[4:]):
            self.assertNotEqual(bank.save_gap('new gap'), gap)
        bank.update_status('keep')
        bank.clear(keep_status=True)
        self.assertEqual(bank.status, 'keep')
        self.assertEqual(bank.entries, [])
        self.assertTrue(bank.tombstones)
        bank.validate_bank()

    def test_source_body_once_and_uncited_not_retained(self):
        bank = EvidenceGapMemory()
        long_text = 'long public source ' * 100
        for i in range(12):
            draft = bank.fork_write_draft()
            parts, refs = self.parts(str(i), long_text)
            draft.retain_manifest(parts)
            draft.apply_bound_write('knowledge', 'fact', refs, cycle_id=str(i), op_index=0)
            bank.publish(bank.prepare_publication(draft))
        evidence = json.dumps(bank.to_dict()['gap_evidence'])
        self.assertEqual(evidence.count(long_text), 1)
        draft = bank.fork_write_draft()
        parts, _ = self.parts('unused', 'UNUSED LONG SOURCE')
        draft.retain_manifest(parts)
        bank.publish(bank.prepare_publication(draft))
        self.assertNotIn('UNUSED LONG SOURCE', json.dumps(bank.to_dict()))
        self.assertFalse(hasattr(bank, '_pending_visibility'))

    def test_legacy_and_corrupt_load(self):
        legacy = GapMemory()
        legacy.save_knowledge('unbound')
        loaded = EvidenceGapMemory.from_dict(legacy.to_dict())
        self.assertEqual(len(loaded.receipts), 0)
        bank = EvidenceGapMemory()
        self.write(bank)
        for damage in ('schema', 'receipt', 'blob', 'active', 'identity'):
            data = bank.to_dict()
            e = data['gap_evidence']
            if damage == 'schema': e['schema'] = 999
            elif damage == 'receipt': e['receipts'] = {}
            elif damage == 'blob': e['blobs'][next(iter(e['blobs']))] = 'tampered'
            elif damage == 'active': e['active_revisions']['absent'] = next(iter(e['revisions']))
            else: e['revisions'][next(iter(e['revisions']))]['revision_id'] = 'wrong'
            with self.assertRaises(ValueError, msg=damage):
                EvidenceGapMemory.from_dict(data)

    def test_writer_failure_and_intervening_write_reject_publication(self):
        bank = EvidenceGapMemory()
        self.write(bank)
        before = bank.to_dict()
        for kind in ('knowledge', 'procedural', 'gap', 'status'):
            draft = bank.fork_write_draft()
            parts, refs = self.parts('fail')
            draft.retain_manifest(parts)
            draft.delete_bound(bank.knowledge[0].id)
            writer = 'update_status' if kind == 'status' else 'save_' + kind
            with patch.object(draft, writer, side_effect=RuntimeError('writer failed')):
                with self.assertRaises(RuntimeError):
                    draft.apply_bound_write(kind, 'new', refs, cycle_id='fail', op_index=0)
            self.assertEqual(before, bank.to_dict())
        draft = bank.fork_write_draft()
        bank.save_procedural('intervening write')
        with self.assertRaises(ValueError):
            bank.prepare_publication(draft)

    def test_checkpoint_failures_leave_old_json_and_no_cycle_save(self):
        bank = EvidenceGapMemory()
        with patch.object(bank, 'save_to_file', side_effect=AssertionError('per-cycle save')):
            self.write(bank)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'memory.json'
            target.write_text('{"old":true}')
            for call in ('source_memory.json.dump', 'source_memory.os.fsync', 'source_memory.os.replace'):
                with patch(call, side_effect=OSError('injected')):
                    with self.assertRaises(OSError): bank.save_to_file(target)
                self.assertEqual(json.loads(target.read_text()), {'old': True})
            bank.save_to_file(target)
            self.assertEqual(json.loads(target.read_text()), json.loads(json.dumps(bank.to_dict())))
            self.assertEqual(list(Path(folder).iterdir()), [target])


if __name__ == '__main__':
    unittest.main()
