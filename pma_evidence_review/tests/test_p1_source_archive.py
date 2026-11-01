"""Source associations and identity boundaries, not claim truth tests."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

from pma_evidence_review.tests.test_bank_display import STAGE
from p1_source_archive import SourceArchive, MAX_SOURCE_RETURN_CHARS, digest, encode


class SourceArchiveTests(unittest.TestCase):
    def archive(self, root):
        return SourceArchive(root, task_id='task-1', task='Original task')

    def event(self, key='e1', command='query --region west', result='seven rows'):
        row = {'commands': [command], 'observation': {'tool_results': [
            {'tool_use_id': 'query-1', 'content': result}]}, 'analysis': 'Actor report'}
        if key is not None:
            row['event_id'] = key
        return row

    def test_repeated_ids_distinct_executions_and_unknown_ids_keep_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.archive(tmp)
            events = [self.event(), self.event(), self.event('e2'), self.event(None), self.event(None)]
            rows = a.classify(events)
            self.assertEqual([r['presentation'] for r in rows],
                ['new_event','repeated_in_window','new_event','identity_unknown','identity_unknown'])
            self.assertEqual(len(rows), 5)
            a.mark_presented(rows)
            self.assertEqual(a.classify([self.event()])[0]['presentation'], 'previously_presented')
            self.assertEqual(self.archive(tmp).classify([self.event('e2')])[0]['presentation'], 'previously_presented')
            with self.assertRaises(ValueError):
                a.classify([self.event(command='query --region east')])

    def test_window_is_exact_immutable_and_restored_association_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.archive(tmp)
            rows = a.classify([self.event()])
            a.capture('cycle1', '  full input\r\n parameter=west; result=seven rows', rows)
            a.bind('m1','knowledge','saved', 'cycle1')
            before = {p.relative_to(tmp): p.read_bytes() for p in Path(tmp).rglob('*') if p.is_file()}
            restored = self.archive(tmp)
            records = {'m1': NS(category='knowledge',content='saved')}
            reply = json.loads(restored.read('m1',records))
            self.assertEqual(reply['status'],'available')
            self.assertEqual(json.loads(reply['source_text'])['model_input'], '  full input\r\n parameter=west; result=seven rows')
            self.assertEqual(before, {p.relative_to(tmp):p.read_bytes() for p in Path(tmp).rglob('*') if p.is_file()})
            with self.assertRaises(FileExistsError):
                a.capture('cycle1', 'changed', rows)
            with self.assertRaises(ValueError):
                a.bind('m1','knowledge','changed','cycle1')

    def test_absent_legacy_missing_and_deleted_sources_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.archive(tmp)
            records={'m1':NS(category='knowledge',content='saved')}
            self.assertEqual(json.loads(a.read('missing',records))['status'],'entry_not_found')
            self.assertEqual(json.loads(a.read('m1',records))['status'],'source_unrecorded')
            a.capture('cycle1','input',[]);a.bind('m1','knowledge','saved','cycle1')
            a.window_path('cycle1').unlink()
            self.assertEqual(json.loads(a.read('m1',records))['status'],'source_missing')
            self.assertEqual(json.loads(a.read('m1',{}))['status'],'entry_not_found')
            self.assertTrue((Path(tmp)/'entry_sources.jsonl').exists())

    def test_wrong_task_id_category_content_cycle_and_corrupt_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=self.archive(tmp);a.capture('c1','input',[]);a.bind('m1','knowledge','saved','c1')
            records={'m1':NS(category='knowledge',content='saved')}
            ref=deepcopy(a.refs['m1'])
            for field,value in [('task_id','other'),('memory_id','m2'),('category','gap'),('content_sha256','wrong')]:
                a.refs['m1']={**ref,field:value}
                self.assertEqual(json.loads(a.read('m1',records))['status'],'source_binding_error')
            a.refs['m1']=ref
            window=json.loads(a.window_path('c1').read_text());window['cycle_id']='other'
            text=encode(window);a.window_path('c1').write_text(text)
            a.refs['m1']['window_sha256']=digest(text)
            self.assertEqual(json.loads(a.read('m1',records))['status'],'source_binding_error')
            a.window_path('c1').write_text('corrupt')
            self.assertEqual(json.loads(a.read('m1',records))['status'],'source_integrity_error')
            with self.assertRaises(ValueError):
                SourceArchive(tmp, task_id='other-task',task='Other task')
            with self.assertRaises(ValueError):
                a.window_path('../escape')

    def test_full_serialized_receipt_limit_and_truncation_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=self.archive(tmp)
            a.capture('c1','\"\n中' * 12000,[]);a.bind('m1','knowledge','saved','c1')
            raw=a.read('m1',{'m1':NS(category='knowledge',content='saved')})
            self.assertLessEqual(len(raw),MAX_SOURCE_RETURN_CHARS)
            reply=json.loads(raw)
            self.assertEqual(reply['status'],'available_truncated')
            self.assertTrue(reply['truncated'])
            self.assertGreater(reply['source_characters'],len(reply['source_text']))
