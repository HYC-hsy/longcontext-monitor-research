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
    return len(row['text']) if 'text' in row else sum(p['end']-p['start'] for p in row.get('segments',[]))


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
        self.assertTrue(any(r['field']=='observation.content' and r.get('omitted_ranges') for r in rows)
                        or rows[0]['omitted_roles'].get('actor_history',0)>0)

    def test_wide_dict_and_many_receipts_have_full_serialized_hard_cap(self):
        for n in (1000,5000):
            body={'stdout':'visible output','exit_code':0,**{'key_'+str(i):'x' for i in range(n)}}
            rows,_=project({'commands':['run'],'observation':json.dumps({'content':'actor',
                'tool_results':[{'tool_use_id':'a','content':json.dumps(body)}]})})
            self.assertLessEqual(len(encode(rows)),rows[0]['serialized_limit'])
            self.assertEqual(rows[0]['unclassified_field_count'],n)
            self.assertLessEqual(len(rows),17)
            self.assertIn('raw_read',rows[0])
        outer={'tool_use_id':'a','stdout':'output',**{'other_'+str(i):'x' for i in range(1000)}}
        rows,_=project({'commands':['run'],'observation':json.dumps({'content':'actor','tool_results':[outer]})})
        self.assertEqual(rows[0]['unclassified_field_count'],1000)
        self.assertLessEqual(len(encode(rows)),rows[0]['serialized_limit'])
        rows,_=project({'commands':['run'],'observation':json.dumps({'content':'actor','tool_results':[{}]*1000})})
        self.assertLessEqual(len(encode(rows)),rows[0]['serialized_limit'])
        self.assertEqual(rows[0]['receipt_count'],1000)
        self.assertGreater(rows[0]['unshown_receipt_count'],0)
        self.assertTrue(rows[0]['omitted_row_ranges'])

    def test_empty_and_identity_only_receipts_are_not_absent(self):
        rows,_=project({'commands':[{'id':'a'}],'observation':json.dumps({'content':'actor',
            'tool_results':[{}, {'tool_use_id':'a'}]})})
        self.assertEqual(rows[0]['receipt_count'],2)
        empty=[r for r in rows if r['role']=='receipt_present_no_content']
        self.assertEqual(len(empty),2)
        self.assertEqual(empty[1]['identity_fields'],{'tool_use_id':'a'})
        self.assertEqual(empty[1]['paired_command_indices'],[0])
        self.assertTrue(rows[0]['original_read_not_implied'])
        self.assertEqual(rows[0]['via'],'selected')
        self.assertEqual(rows[0]['order_basis'],'host_acceptance')

    def test_line_aligned_fragments_and_short_stdout_keep_full_failure_context(self):
        text=''.join('line '+str(i)+'🙂\r\n' for i in range(300))
        row=excerpt(text,240)
        for part in row['segments']:
            self.assertEqual(part['text'],text[part['start']:part['end']])
            self.assertFalse(part['starts_mid_line']);self.assertFalse(part['ends_mid_line'])
        line=excerpt('🙂'*10000,240)
        self.assertTrue(line['preview_only'])
        self.assertTrue(any(p['starts_mid_line'] or p['ends_mid_line'] for p in line['segments']))
        data=json.loads((FIX/'01-local-success-scope.json').read_text())
        rows,_=project(data['raw'],data['call_links'])
        stdout=next(r for r in rows if r['field'].endswith('.stdout'))
        original=json.loads(json.loads(data['raw']['observation'])['tool_results'][0]['content'])['stdout']
        self.assertEqual(stdout.get('text'),original)
        self.assertFalse(stdout['preview_only'])
        self.assertIn('bash: line 13: sqlite3: command not found',stdout['text'])
        self.assertLessEqual(len(encode(rows)),rows[0]['serialized_limit'])
