import copy
import json
import unittest

from pma_evidence_review import citation_inputs as ci
from pma_evidence_review.inputs import digest
from pma_evidence_review.tests.fixtures import packet
from pma_evidence_review.tests.no_network import install_guard


def aligned(parent=None):
    p=parent or packet()
    op=p['operations'][0];s=p['sources'][2];piece=s['slices'][0]
    ref={'source_id':s['source_id'],'role':s['role'],'order':s['event_order'],
        'source_kind':s['kind'],'visibility_ref':s['visibility_ref'],
        'start':piece['start'],'end':piece['end'],'snippet_sha256':digest(piece['text']),
        'source_text_sha256':digest(piece['text'])}
    data={'status':'exact_unique','bound_refs':[ref],'items':[{'quote':piece['text'],'source_hint':None,
        'status':'exact_unique','reason':None,'metadata':{},'candidates':[ref]}]}
    row={'cycle_id':p['cycle_id'],'revision_id':op['revision_id'],'status':'exact_unique',
         'alignment_json':json.dumps(data)}
    return p,{op['revision_id']:row}


class CitationInputTests(unittest.TestCase):
    def setUp(self): install_guard(self)

    def test_real_operations_and_actual_binding_identity(self):
        for sample,statuses,counts in [('sqlite',['ready','not_applicable_delete_protocol','citation_set_not_eligible'],[3,0,3]),
            ('html',['ready','not_applicable_delete_protocol','citation_set_not_eligible','citation_set_not_eligible'],[1,0,3,2])]:
            p=ci.build('.',sample)
            self.assertEqual([r['preparation']['status'] for r in p['operations']],statuses)
            self.assertEqual([len(r['preparation']['citations']) for r in p['operations']],counts)
            self.assertNotEqual(p['citation_input_sha256'],p['parent_input_sha256'])
            self.assertIsNone(p['operations'][1]['recovered_alignment'])
            for row in p['operations']:
                for item in row['preparation']['citations']:
                    for bound in item['candidates']:
                        self.assertNotIn('validation_error',bound)
                        self.assertEqual(digest(bound['original_excerpt']),bound['reference']['snippet_sha256'])
            if sample=='html':
                c=p['operations'][0]['preparation']['citations'][0]['candidates'][0]
                self.assertEqual(c['reference']['role'],'tool_command')
                self.assertEqual((c['reference']['start'],c['reference']['end']),(4885,4934))
                self.assertEqual(c['field_path'],'commands/0/args/content')
            else:
                fuzzy=p['operations'][2]['preparation']['citations'][2]
                self.assertEqual(fuzzy['binding_status'],'fuzzy_candidate')
                self.assertEqual(len(fuzzy['candidates']),2)
                self.assertTrue(all(c['original_excerpt']!=fuzzy['submitted_quote'] for c in fuzzy['candidates']))

    def test_no_missing_malformed_ambiguous_and_unmatched_preserved(self):
        p,rows=aligned();rid=p['operations'][0]['revision_id']
        for raw,status in [(None,'evidence_unavailable'),('invalid','malformed_evidence_unavailable'),
            ({**rows[rid],'alignment_json':'bad'},'malformed_evidence_unavailable'),
            ({**rows[rid],'alignment_json':json.dumps({'items':[],'bound_refs':[],'reason':'no_evidence','status':'unbound'})},'no_evidence')]:
            result=ci.build_from_parent(p,{rid:raw})
            self.assertEqual(result['operations'][0]['preparation']['status'],status)
        for status in ('fuzzy_candidate','exact_multiple','unbound'):
            raw=copy.deepcopy(rows[rid]);data=json.loads(raw['alignment_json'])
            data['items'][0]['status']=status
            if status=='exact_multiple': data['items'][0]['candidates']*=2
            if status=='unbound': data['items'][0]['candidates']=[]
            raw['alignment_json']=json.dumps(data)
            prepared=ci.build_from_parent(p,{rid:raw})['operations'][0]['preparation']
            self.assertEqual(prepared['status'],'citation_set_not_eligible')
            self.assertEqual(prepared['citations'][0]['binding_status'],status)

    def test_tamper_and_recomputed_hash_cannot_bypass_preparation(self):
        p,rows=aligned();result=ci.build_from_parent(p,rows)
        changed=copy.deepcopy(result)
        changed['operations'][0]['preparation']['citations'][0]['submitted_quote']='different'
        with self.assertRaisesRegex(ValueError,'citation_input_hash'): ci.validate(changed)
        changed['citation_input_sha256']=ci.identity({k:v for k,v in changed.items() if k!='citation_input_sha256'})
        with self.assertRaisesRegex(ValueError,'preparation_mismatch'): ci.validate(changed)
        rid=p['operations'][0]['revision_id']
        for field,value in [('role','tool_command'),('start',-1),('snippet_sha256','0'*64),('visibility_ref','bad')]:
            raw=copy.deepcopy(rows[rid]);data=json.loads(raw['alignment_json'])
            data['items'][0]['candidates'][0][field]=value;raw['alignment_json']=json.dumps(data)
            out=ci.build_from_parent(p,{rid:raw})
            self.assertEqual(out['operations'][0]['preparation']['status'],'citation_set_not_eligible')
        altered=copy.deepcopy(rows)
        data=json.loads(altered[rid]['alignment_json']);data['items'][0]['quote']='changed quote'
        altered[rid]['alignment_json']=json.dumps(data)
        self.assertNotEqual(ci.build_from_parent(p,altered)['citation_input_sha256'],result['citation_input_sha256'])

    def test_order_and_duplicates_remain_submitted_entries(self):
        p,rows=aligned();rid=p['operations'][0]['revision_id'];data=json.loads(rows[rid]['alignment_json'])
        data['items']*=2;rows[rid]['alignment_json']=json.dumps(data)
        ready=ci.build_from_parent(p,rows)['operations'][0]['preparation']
        self.assertEqual(ready['status'],'ready')
        self.assertEqual([r['citation_index'] for r in ready['citations']],[0,1])
        self.assertEqual(ready['citations'][0]['submitted_quote'],ready['citations'][1]['submitted_quote'])

    def test_malformed_and_inconsistent_records_never_request(self):
        from pma_evidence_review.citation_review import requests
        p,rows=aligned();rid=p['operations'][0]['revision_id']
        for mutate in ('duplicate','hint','future','bound_refs'):
            raw=copy.deepcopy(rows[rid]);d=json.loads(raw['alignment_json'])
            if mutate=='hint': d['items'][0]['source_hint']={}
            if mutate=='future': d['items'][0]['candidates'][0]['parent_revision_id']='future_revision'
            if mutate=='bound_refs': d['bound_refs']=[]
            raw['alignment_json']=json.dumps(d)
            if mutate=='duplicate': raw['alignment_json']=raw['alignment_json'].replace('"status": "exact_unique"','"status":"unbound","status":"exact_unique"',1)
            result=ci.build_from_parent(p,{rid:raw})
            self.assertNotEqual(result['operations'][0]['preparation']['status'],'ready')
            self.assertIsNone(requests(result)[0]['request'])

    def test_source_digest_known_record_and_partial_visibility(self):
        p=ci.build('.', 'html');row=p['operations'][0];parent=p['host_provenance']
        ref=copy.deepcopy(row['preparation']['citations'][0]['candidates'][0]['reference'])
        ref['source_text_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'source_hash_mismatch'):
            ci.candidate(ref,parent,p['source_records'])
        # No complete record: partial excerpt cannot validate a full-source digest.
        partial=copy.deepcopy(parent)
        source=next(s for s in partial['sources'] if s['source_id']==ref['source_id'])
        original=source['slices'][0]
        source['slices']=[{'start':ref['start'],'end':ref['end'],
            'text':original['text'][ref['start']-original['start']:ref['end']-original['start']]}]
        self.assertEqual(ci.candidate(ref,partial)['source_text_hash_check'],
                         'full_source_unavailable_not_asserted')
