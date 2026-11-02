"""Projection checks only, not model behavior or semantic success scoring."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from types import SimpleNamespace as NS
from pma_evidence_review.tests.test_bank_display import ROOT
from p1_dms_view import material_previews,excerpt
from p1_dms_agent import DMSMaterialStore
from p1_source_archive import split_visible_observation,encode
from p1_source_links import call_links
import tempfile

def shown(row):
    return len(row['text']) if 'text' in row else sum(p['end']-p['start'] for p in row['segments'])


FIX=ROOT/'pma_evidence_review/tests/fixtures/dms_receipts'


def project(raw,links=None):
    with tempfile.TemporaryDirectory() as root:
        store=DMSMaterialStore(root,task_id='task',task='requirement',bank={'status':'','knowledge':[],'procedural':[],'gaps':[]})
        store.ingest([raw]);sid='event_1'
        if links is not None:store.state['events'][sid]['call_links']=links
        before=deepcopy(store.state)
        rows=material_previews(store,[{'source_id':sid,'via':'selected'}])
        assert store.state==before
        return rows,store._fields([{'source_id':sid,'via':'selected'}])


class ReceiptViewTests(unittest.TestCase):
    def test_real_B01_B04_raw_failures_and_actions_visible_after_storage(self):
        for name,word in [('01-local-success-scope','command not found'),('04-counterevidence-to-old-claim','Segmentation fault')]:
            data=json.loads((FIX/(name+'.json')).read_text())
            rows,full=project(data['raw'],data['call_links'])
            receipts=[r for r in rows if 'receipt' in r['role']]
            self.assertIn(word,json.dumps(receipts,ensure_ascii=False))
            self.assertTrue(any(r['role']=='actions_and_parameters' and shown(r) for r in rows))
            self.assertTrue(any(r.get('pairing')=='explicit' and r['paired_command_indices'] for r in receipts))
            self.assertTrue(any(r['field'].endswith('.status') and r.get('text',''.join(s['text'] for s in r.get('segments',[])))=='success' for r in receipts))
            observation=next(t for _,f,_,t in full if f=='observation')
            self.assertEqual(observation,data['raw']['observation'])
            for r in rows:
                if 'segments' not in r:continue
                self.assertEqual(sum(s['end']-s['start'] for s in r['segments']),shown(r))

    def test_multiple_calls_do_not_cross_pair_or_turn_shell_success_into_task_success(self):
        raw={'event_id':'e','commands':[{'id':'a','args':{'x':1}},{'id':'b','args':{'x':2}}],
            'analysis':'Actor says all done','observation':json.dumps({'content':'[WORKING MEMORY] old history',
            'tool_results':[{'tool_use_id':'b','status':'success','content':json.dumps({'exit_code':0,'stdout':'literal failure b','stderr':'warning'})},
                            {'tool_use_id':'a','content':json.dumps({'stdout':'literal failure a','status':'success'})}]})}
        rows,_=project(raw)
        for r in rows:
            if r.get('receipt_index')==0 and 'paired_command_indices' in r:self.assertEqual(r['paired_command_indices'],[1])
            if r.get('receipt_index')==1 and 'paired_command_indices' in r:self.assertEqual(r['paired_command_indices'],[0])
        self.assertIn('literal failure',json.dumps(rows))
        self.assertTrue(any(r['field'].endswith('exit_code') and r.get('text',''.join(s['text'] for s in r.get('segments',[])))=='0' for r in rows))
        self.assertTrue(all(r['role'].startswith('actor_') for r in rows if r['field'] in ('analysis','observation.content')))
        self.assertNotIn('task_success',json.dumps(rows))

    def test_unknown_long_unicode_missing_receipts_and_ranges_are_explicit(self):
        text=' 甲🙂\r\n\t '*5000
        raw={'commands':['run'],'observation':text,'analysis':'actor only'}
        rows,full=project(raw)
        unknown=next(r for r in rows if r['role']=='unclassified_observation')
        self.assertTrue(unknown['preview_only']);self.assertTrue(unknown['omitted_ranges'])
        for part in unknown['segments']:
            self.assertEqual(part['text'],text[part['start']:part['end']])
        self.assertEqual(next(t for _,f,_,t in full if f=='observation'),text)
        rows,_=project({'commands':['run'],'observation':json.dumps({'content':'actor','tool_results':[]})})
        self.assertTrue(any(r['role']=='no_tool_receipts' for r in rows))
        known,_,_=split_visible_observation({'content':'x','tool_results':[],'other':1})
        self.assertFalse(known)
        for size in (0,1,2,7,100):
            v=excerpt('🙂\t\n ABC',size)
            self.assertLessEqual(shown(v),size)

    def test_actor_history_cannot_take_receipt_allocation_and_preview_is_readonly(self):
        raw={'event_id':'e','commands':['execute --arg=exact'],
             'analysis':'actor '*10000,'observation':json.dumps({'content':'history '*20000,
                 'tool_results':[{'tool_use_id':'unknown','content':json.dumps({'stdout':'receipt '*500,'stderr':'end error','exit_code':0})}]})}
        rows,_=project(raw)
        self.assertTrue(any(r['field'].endswith('stderr') and 'end error' in str(r) for r in rows))
        self.assertTrue(all(not r.get('paired_command_indices',[]) for r in rows if r.get('receipt_index')==0))
        self.assertLessEqual(sum(shown(r) for r in rows),rows[0]['source_event_text_budget'])
        self.assertTrue(any(r['field']=='observation.content' and r['omitted_ranges'] for r in rows))
