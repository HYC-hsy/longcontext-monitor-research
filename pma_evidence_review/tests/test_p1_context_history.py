"""Window-local input coverage; no model/provider execution."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from pma_evidence_review.tests.test_bank_display import GapMemory
from pma_evidence_review.tests.no_network import install_guard
from p1_context_agent import ContextSourceP1Agent
from p1_context_history import InputMemoryHistory, HistoryError
from p1_source_archive import encode


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        bank=GapMemory();self.old=bank.save_knowledge('known A')
        self.a=ContextSourceP1Agent(task='task',task_id='t',memory=bank,llm=None,source_root=self.temp.name)
        self.h=InputMemoryHistory(self.a.links,self.a.source_archive)
        self.a.source_archive.capture('origin','A original query\r\n🙂',[])
        state=deepcopy(self.a.links.state)
        self.a.links.bind_state(state,self.old,'knowledge','known A',{
            'sources':[],'inherited_unassociated':[],'association':'legacy_unassociated'},'origin')
        self.a.links.commit(state)

    def child(self, count=1):
        oldref=deepcopy(self.a.links.state['refs'][self.old])
        records=[self.h.record(self.old if i==0 else 'old_'+str(i),'knowledge',
            'known A' if i==0 else '长🙂\r\n'*100,None if i else oldref) for i in range(count)]
        self.a.source_archive.capture('child','A+B generation input',[],
            input_memory_coverage=self.h.coverage(records,[]))
        key=self.a.memory.save_knowledge('A+B summary')
        state=deepcopy(self.a.links.state)
        self.a.links.bind_state(state,key,'knowledge','A+B summary',{
            'sources':[],'inherited_unassociated':[],'association':'unassociated'},'child')
        state['bank']=self.a.memory.to_dict();self.a.links.commit(state)
        return {'kind':'memory','id':key,'ref':deepcopy(state['refs'][key])}

    def test_issued_snapshot_survives_delete_and_reopens(self):
        target=self.child()
        page=self.h.read(target,self.a._active_records())
        self.assertEqual((page['requested_view'],page['resolved_view']),('auto','context'))
        import json
        token=next(json.loads(p['text'])['history_handle'] for p in page['parts'] if p['field']=='input_memory')
        self.assertEqual(self.h.load(token)['memory_id'],self.old)
        self.a.memory.delete(self.old)
        state=deepcopy(self.a.links.state);state['refs'].pop(self.old);state['bank']=self.a.memory.to_dict()
        self.a.links.commit(state)
        read=self.h.read(None,{},handle=token)
        text=''.join(p['text'] for p in read['parts'] if p['field']=='model_input')
        self.assertEqual(text,'A original query\r\n🙂')
        self.assertFalse(read['complete'])
        reopened=ContextSourceP1Agent(task='task',task_id='t',memory=GapMemory.from_dict(self.a.memory.to_dict()),
            llm=None,source_root=self.temp.name)
        self.assertEqual(InputMemoryHistory(reopened.links,reopened.source_archive).load(token)['content'],'known A')
        with self.assertRaises(HistoryError):
            self.h.load(token+'x')

    def test_large_directory_atomic_paging_grants_only_returned_handles(self):
        target=self.child(100)
        fields,pending,_=self.h._directory(target['ref'])
        page=self.h.read(target,self.a._active_records(),requested_view='context')
        self.assertLessEqual(len(encode(page)),8000)
        grants=self.a.links.state['history_grants']
        self.assertLess(len(grants),len(pending))
        not_issued=next(h for h in pending if h not in grants)
        with self.assertRaises(HistoryError):
            self.h.load(not_issued)
        returned=[];cursor=None
        for _ in range(100):
            page=self.h.read(target,self.a._active_records(),requested_view='context',cursor=cursor)
            self.assertLessEqual(len(encode(page)),8000)
            for part in page['parts']:
                if part['field']=='input_memory':
                    self.assertEqual((part['start'],part['end']),(0,part['total']))
                    returned.append(part['source_id'])
            cursor=page['next_cursor']
            if cursor is None:break
        self.assertEqual(len(returned),100)
        self.assertEqual(len(set(returned)),100)
        self.assertEqual(len(self.a.links.state['history_grants']),100)
        self.a.source_archive.window_path('child').write_bytes(b'corrupt')
        with self.assertRaises(HistoryError):
            self.h.load(not_issued)
