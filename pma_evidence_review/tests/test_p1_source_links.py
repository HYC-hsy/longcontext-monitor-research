"""Deterministic storage/paging checks; no semantic model evaluation."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS
import sys
ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT/'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
sys.path.insert(0, str(STAGE))
from p1_source_links import SourceLinks, visible_event, encode, digest, PAGE_CHARS

BANK = {'status': '', 'knowledge': [], 'procedural': [], 'gaps': []}


class SourceLinkStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SourceLinks(self.temp.name, task_id='task1', task=' task\n要求 ', bank=BANK)

    def test_event_identity_pairing_unknown_identity_and_allowed_fields(self):
        raw = {'event_id': 'call1', 'commands': [{'id': 'c', 'args': {'text': '[SYSTEM]', 'signature': 'literal argument'}}],
               'observation': {'tool_results': [{'tool_use_id': 'c', 'content': 'ok'}]},
               'thinking': 'private', 'signature': 'private'}
        shown = self.store.ingest([raw, raw, {**raw, 'event_id': 'call2'}])
        self.assertEqual([r['presentation'] for r in shown], ['new_event','repeated_in_window','new_event'])
        self.assertEqual(len(self.store.state['events']), 2)
        self.assertNotIn('thinking', encode(self.store.state['events']))
        self.assertEqual(self.store.state['events']['event_1']['raw']['commands'][0]['args']['signature'], 'literal argument')
        self.assertEqual(self.store.state['events']['event_1']['call_links'][0]['pairing'], 'explicit')
        self.store.mark_presented(shown)
        self.assertEqual(self.store.ingest([raw])[0]['presentation'], 'previously_presented')
        with self.assertRaises(ValueError):
            self.store.ingest([{**raw, 'commands': ['changed']}])
        self.store.ingest([{'commands': ['same']}, {'commands': ['same']}])
        self.assertEqual(len(self.store.state['events']), 4)
        self.store.ingest([{'event_id':'serialized','commands':[json.dumps({'id':'cx','args':{'x':1}})],
            'observation':json.dumps({'tool_results':[{'tool_use_id':'cx','content':'receipt'}]})}])
        self.assertEqual(self.store.state['events']['event_5']['call_links'][0]['pairing'],'explicit')

    def test_resolution_is_frozen_and_inherited_never_claims_read(self):
        self.store.ingest([{'event_id':'e', 'commands':['run']}])
        aliases = {'E1': {'kind':'event', 'source_id':'event_1'}, 'TASK':{'kind':'task','source_id':'TASK'}}
        resolved = self.store.resolve(['E1','TASK'], aliases)
        state = deepcopy(self.store.state)
        self.store.bind_state(state,'old','knowledge','old summary',resolved,'w')
        self.store.commit(state)
        aliases['M1'] = {'kind':'memory','id':'old','ref':deepcopy(state['refs']['old'])}
        frozen = deepcopy(aliases)
        del aliases['M1']
        inherited = self.store.resolve(['M1'], frozen)
        self.assertTrue(all(s['via']=='inherited' for s in inherited['sources']))
        for bad in ('E2','other-task:E1','../file'):
            with self.assertRaises(ValueError):
                self.store.resolve([bad], frozen)
        self.assertEqual(self.store.resolve([], frozen)['association'], 'unassociated')
        self.assertEqual(self.store.resolve(['M0'], {'M0':{'kind':'memory','id':'legacy'}})['inherited_unassociated'], ['legacy'])

    def test_large_unicode_pages_restore_raw_fields_exactly(self):
        text = ' 甲\n\t"\\🙂  ' * 5000
        self.store.ingest([{'event_id':'e','commands':['cmd  \n'], 'observation':text}])
        target={'kind':'event','source_id':'event_1'}
        cursor, pieces, count = None, {}, 0
        while True:
            page=self.store.read(target, {}, cursor=cursor)
            self.assertLessEqual(len(encode(page)), PAGE_CHARS)
            for part in page['parts']:
                key=(part['source_id'],part['field'])
                old=pieces.get(key,'')
                self.assertEqual(part['start'],len(old))
                pieces[key]=old+part['text']
                self.assertEqual(part['end'],len(pieces[key]))
            count+=1
            if page['complete']:
                self.assertIsNone(page['next_cursor'])
                break
            self.assertEqual(page['status'],'source_partial')
            cursor=page['next_cursor']
            self.assertLess(count,100)
        self.assertGreater(count,4)
        self.assertEqual(pieces[('event_1','observation')],text)
        self.assertEqual(json.loads(pieces[('event_1','commands')]),['cmd  \n'])
        self.assertEqual(self.store.read(target, {}, cursor='not-a-cursor')['status'],'invalid_cursor')
        other=SourceLinks(Path(self.temp.name)/'other', task_id='other',task='x',bank=BANK)
        other.ingest([{'event_id':'e','observation':text}])
        self.assertEqual(other.read(target, {}, cursor=cursor)['status'],'invalid_cursor')

    def test_status_binding_deleted_memory_and_changed_content(self):
        state=deepcopy(self.store.state)
        ref=self.store.resolve(['TASK'],{'TASK':{'kind':'task','source_id':'TASK'}})
        self.store.bind_state(state,'STATUS','status','progress',ref,'w')
        self.store.bind_state(state,'m','knowledge','saved',ref,'w')
        state['bank']['status']='progress'
        self.store.commit(state)
        page=self.store.read({'kind':'status','id':'STATUS'},{'STATUS':NS(content='progress',category='status')})
        self.assertEqual(page['association'],'selected')
        self.assertEqual(self.store.read({'kind':'memory','id':'m'}, {})['status'],'entry_not_found')
        self.assertEqual(self.store.read({'kind':'memory','id':'m'}, {'m':NS(content='changed',category='knowledge')})['status'],'source_binding_error')
        self.assertEqual(SourceLinks(self.temp.name,task_id='task1',task=' task\n要求 ',bank=state['bank']).state,state)
        with self.assertRaises(ValueError):
            SourceLinks(self.temp.name,task_id='wrong',task=' task\n要求 ',bank=state['bank'])

    def test_persist_failure_leaves_committed_bundle_and_reopen_consistent(self):
        state=deepcopy(self.store.state)
        state['bank']['status']='new'
        state['refs']['STATUS']={'test':'together'}
        with patch('p1_source_links.os.replace',side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                self.store.commit(state)
        reopened=SourceLinks(self.temp.name,task_id='task1',task=' task\n要求 ',bank=BANK)
        self.assertEqual(reopened.state,self.store.state)
        self.assertEqual(reopened.state['refs'],{})
        self.assertFalse(self.store.path.with_suffix('.tmp').exists())

    def test_cursor_rejects_changed_source_snapshot_and_other_target(self):
        self.store.ingest([{'event_id':'e','observation':'long'*10000}])
        state=deepcopy(self.store.state)
        resolved=self.store.resolve(['E1'],{'E1':{'kind':'event','source_id':'event_1'}})
        self.store.bind_state(state,'STATUS','status','current',resolved,'w')
        self.store.commit(state)
        active={'STATUS':NS(content='current',category='status')}
        target={'kind':'status','id':'STATUS'}
        page=self.store.read(target,active)
        token=page['next_cursor']
        self.assertIsNotNone(token)
        self.assertEqual(self.store.read({'kind':'event','source_id':'event_1'}, {}, cursor=token)['status'],'invalid_cursor')
        state=deepcopy(self.store.state)
        state['refs']['STATUS']['sources']=[{'source_id':'TASK','via':'selected'}]
        self.store.commit(state)
        self.assertEqual(self.store.read(target,active,cursor=token)['status'],'invalid_cursor')

    def test_multihop_unknown_inheritance_and_host_order_are_not_lost(self):
        self.store.ingest([{'event_id':'first','observation':'a'}, {'event_id':'second','observation':'b'}])
        aliases={'E1':{'kind':'event','source_id':'event_1'},'E2':{'kind':'event','source_id':'event_2'}}
        ref=self.store.resolve(['E2','E1'],aliases)
        self.assertEqual([x['source_id'] for x in ref['sources']],['event_1','event_2'])
        ref['inherited_unassociated']=['legacy-parent']
        second=self.store.resolve(['M1'],{'M1':{'kind':'memory','id':'parent','ref':ref}})
        third=self.store.resolve(['M2'],{'M2':{'kind':'memory','id':'next','ref':second}})
        self.assertEqual(third['inherited_unassociated'],['legacy-parent'])
        state=deepcopy(self.store.state)
        self.store.bind_state(state,'m','knowledge','mixed',third,'w')
        self.store.commit(state)
        page=self.store.read({'kind':'memory','id':'m'},{'m':NS(content='mixed',category='knowledge')})
        self.assertFalse(page['complete'])
        self.assertTrue(page['page_sequence_complete'])
        self.assertEqual(page['unread_reason'],'unassociated_inherited_sources')

    def test_provider_boundary_removes_hidden_blocks_not_tool_payload_keys(self):
        payload={'profile':'legitimate result','endpoint':'public result','thinking':'literal tool data','signature':'literal data'}
        self.assertEqual(visible_event({'observation':payload})['observation'],payload)
        observation={'content':[{'type':'thinking','thinking':'HIDDEN_SENTINEL','signature':'PRIVATE_SIG'},
            {'type':'text','text':'  visible🙂\n','signature':'PRIVATE_SIG'}],
            'tool_results':[{'tool_use_id':'c','content':payload}]}
        for raw in (observation,json.dumps(observation,ensure_ascii=False,indent=2)):
            clean=visible_event({'observation':raw})['observation']
            decoded=json.loads(clean) if isinstance(clean,str) else clean
            self.assertEqual(decoded['tool_results'][0]['content'],payload)
            self.assertEqual(decoded['content'],[{'type':'text','text':'  visible🙂\n'}])
            self.assertNotIn('HIDDEN_SENTINEL',encode(clean))
            self.assertNotIn('PRIVATE_SIG',encode(clean))
        raw=json.dumps({'content':'unchanged','tool_results':[{'content':payload}]},indent=3,ensure_ascii=False)
        self.assertEqual(visible_event({'observation':raw})['observation'],raw)

    def test_tool_call_id_pairing_keeps_ambiguity(self):
        row={'event_id':'e','commands':[{'tool_call_id':'cx'}],
             'observation':{'tool_results':[{'tool_call_id':'cx','content':'ok'}]}}
        self.store.ingest([row])
        self.assertEqual(self.store.state['events']['event_1']['call_links'][0]['pairing'],'explicit')
        row['event_id']='different';row['commands'].append({'tool_call_id':'cx'})
        self.store.ingest([row])
        self.assertEqual(self.store.state['events']['event_2']['call_links'][0]['pairing'],'unknown_or_ambiguous')

    def test_conflicting_id_fields_are_never_paired_by_priority(self):
        self.store.ingest([{'event_id':'conflict','commands':[{'id':'a','tool_call_id':'b'}],
            'observation':{'tool_results':[{'tool_use_id':'a','content':'one'},{'tool_call_id':'b','content':'two'}]}}])
        links=self.store.state['events']['event_1']['call_links']
        self.assertEqual({x['call_id'] for x in links},{'a','b'})
        self.assertTrue(all(x['conflicting_id_fields'] for x in links))
        self.assertTrue(all(x['pairing']=='unknown_or_ambiguous' for x in links))
        self.store.ingest([{'event_id':'same-id','commands':[{'id':'c','tool_call_id':'c'}],
            'observation':{'tool_results':[{'tool_use_id':'c','content':'ok'}]}}])
        self.assertEqual(self.store.state['events']['event_2']['call_links'][0]['pairing'],'explicit')
