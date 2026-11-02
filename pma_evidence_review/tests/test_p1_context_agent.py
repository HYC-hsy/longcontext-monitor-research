"""Frozen context consumer regressions; scripted only, guarded against network."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace as NS
import unittest
from pma_evidence_review.tests.test_bank_display import reply, GapMemory, ROOT, STAGE
from pma_evidence_review.tests.no_network import install_guard
from p1_context_agent import ContextSourceP1Agent, SYSTEM
from p1_linked_agent import LinkedSourceP1Agent, SYSTEM as OLD_SYSTEM, READ_TOOL
from p1_source_archive import encode, digest


class ContextTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.requests = []
        self.responses = []
        async def fake(**kwargs):
            self.requests.append(deepcopy(kwargs))
            return self.responses.pop(0) if self.responses else reply()
        bank = GapMemory()
        bank.save_knowledge('A limit=50')
        self.agent = ContextSourceP1Agent(task='task',task_id='t',memory=bank,
            llm=NS(call=fake),source_root=self.temp.name)

    def save(self, text='B limit=200', linked=True):
        self.responses.append(reply([('memory_update_status',{
            'content':'A50+B200', 'source_ids':['E1'] if linked else []})]))
        result=asyncio.run(self.agent.maintain([{'event_id':'b','observation':text}],cycle_id='c'))
        self.assertEqual(result['status'],'completed')
        self.target={'kind':'status','id':'STATUS', 'ref':deepcopy(self.agent.links.state['refs']['STATUS'])}
        self.agent.request_aliases={'STATUS':self.target}

    def read(self, view='context', cursor=None):
        active=self.agent._active_records()
        active['STATUS']=NS(content=self.agent.memory.status,category='status')
        return self.agent.links.read(self.target,active,view=view,cursor=cursor,archive=self.agent.source_archive)

    def collect(self, view):
        result=[]; cursor=None
        for _ in range(200):
            page=self.read(view,cursor)
            self.assertLessEqual(len(encode(page)),8000)
            result.extend(page['parts'])
            self.assertFalse(page['complete'])
            self.assertEqual(page['truncated'],not page['page_sequence_complete'])
            cursor=page['next_cursor']
            if cursor is None:
                self.assertTrue(page['page_sequence_complete'])
                return result
        self.fail('unbounded paging')

    def test_selected_b_context_recovers_a_and_exact_frozen_input(self):
        self.save()
        source=''.join(p['text'] for p in self.collect('sources'))
        context=''.join(p['text'] for p in self.collect('context'))
        self.assertNotIn('A limit=50',source)
        self.assertIn('B limit=200',source)
        self.assertIn('A limit=50',context)
        self.assertEqual(context,self.requests[0]['prompt'])
        self.agent.source_archive.capture('new','CURRENT WINDOW',[])
        self.assertEqual(context,''.join(p['text'] for p in self.collect('context')))

    def test_lossless_nested_utf_crlf_paging_and_cross_view_cursor(self):
        self.save(encode({'nested':['\r\n🙂中文\t"\\'*8000,{'x':1}]}))
        context=self.collect('context')
        self.assertEqual(''.join(p['text'] for p in context),self.requests[0]['prompt'])
        page=self.read('sources')
        self.assertIsNotNone(page['next_cursor'])
        self.assertEqual(self.read('context',page['next_cursor'])['status'],'invalid_cursor')
        page=self.read('context')
        self.assertEqual(self.read('sources',page['next_cursor'])['status'],'invalid_cursor')
        self.target['id']='other'
        self.assertEqual(self.read('context',page['next_cursor'])['status'],'entry_not_found')

    def test_corrupt_missing_task_and_content_binding_rejected(self):
        self.save()
        path=self.agent.source_archive.window_path('c_r0')
        raw=path.read_bytes()
        path.write_bytes(raw+b' ')
        self.assertEqual(self.read()['status'],'source_binding_error')
        path.write_bytes(b'not json')
        ref=self.agent.links.state['refs']['STATUS']
        ref['context_sha256']=digest('not json'); self.target['ref']=deepcopy(ref)
        self.assertEqual(self.read()['status'],'source_binding_error')
        window=json.loads(raw);window['task_id']='other'
        path.write_bytes(encode(window).encode('utf-8'))
        ref['context_sha256']=digest(encode(window));self.target['ref']=deepcopy(ref)
        self.assertEqual(self.read()['status'],'source_binding_error')
        path.unlink()
        self.assertFalse(self.read()['page_sequence_complete'])
        path.write_bytes(raw)
        ref['context_sha256']=digest(raw.decode());self.target['ref']=deepcopy(ref)
        self.agent.memory.status='changed'
        self.assertEqual(self.read()['status'],'source_binding_error')

    def test_legacy_context_and_missing_window_never_complete(self):
        self.save(linked=False)
        self.assertIn('A limit=50',''.join(p['text'] for p in self.collect('context')))
        self.assertEqual(self.read('sources')['status'],'source_unassociated')
        self.agent.links.state['refs'].pop('STATUS');self.target['ref']=None
        result=self.read()
        self.assertEqual(result['status'],'context_unavailable')
        self.assertFalse(result['complete']);self.assertFalse(result['page_sequence_complete'])

    def test_shared_budget_and_final_write_only(self):
        self.save()
        self.responses.extend([reply([('memory_read_source',{'memory_id':'STATUS','view':v})
            for v in ('sources','context','sources','context','context')]),reply()])
        result=asyncio.run(self.agent.maintain([],cycle_id='next'))
        self.assertEqual((result['reads_used'],result['read_requests']),(4,5))
        self.assertEqual(result['status'],'budget_limited')
        self.assertEqual(len(self.requests[-1]['tools']),5)
        self.assertEqual(self.requests[-2]['system'],SYSTEM)

    def test_old_actual_system_schema_and_frozen_cases_unchanged(self):
        old=LinkedSourceP1Agent(task='task',task_id='old',memory=GapMemory(),llm=self.agent.llm,
            source_root=Path(self.temp.name)/'old')
        asyncio.run(old.maintain([],cycle_id='old'))
        self.assertEqual(self.requests[-1]['system'],OLD_SYSTEM)
        self.assertEqual(self.requests[-1]['tools'][-1],READ_TOOL)
        published=json.loads((ROOT/'pma_evidence_review/source_links_delivery_20261102/TOOL_SCHEMA.json').read_text())
        self.assertEqual(old.get_tools_schema(),published)
        for name in ('source_links_delivery_20261102/SYSTEM.txt',):
            data=(ROOT/'pma_evidence_review'/name).read_bytes()
            self.assertEqual(data,subprocess.check_output(['git','show','eb406f2:pma_evidence_review/'+name],cwd=ROOT))
        changed=subprocess.check_output(['git','diff','eb406f2','--name-only','--',
            'pma_evidence_review/p1_source_read_delivery/cases'],cwd=ROOT,text=True)
        self.assertEqual(changed,'')

    def test_new_candidate_runner_identity_and_six_frozen_scripted_cases(self):
        from pma_evidence_review.tools.run_p1_source_case import source_identity, run_case
        identity=source_identity(strict=False,candidate='source-links-context-v1')
        self.assertEqual(len(identity['source_files']),62)
        added=[p for p in identity['source_files'] if p.endswith('/p1_context_agent.py')]
        self.assertEqual(len(added),1)
        folder=ROOT/'pma_evidence_review/p1_source_read_delivery/cases'
        for item in json.loads((folder/'INDEX.json').read_text())['cases']:
            with self.subTest(case=item['file']),tempfile.TemporaryDirectory() as tmp:
                requests=[]
                async def fake(**kwargs):
                    requests.append(kwargs);return reply()
                result=asyncio.run(run_case(json.loads((folder/item['file']).read_text()),
                    tmp,NS(call=fake),candidate='source-links-context-v1'))
                self.assertEqual(result['status'],'completed')
                config=json.loads((Path(tmp)/'run_config.json').read_text())
                self.assertEqual((config['read_limit'],config['continuation_limit']),(4,2))
                self.assertEqual(len(requests),1)
                self.assertEqual(requests[0]['system'],SYSTEM)
                self.assertIn('view',requests[0]['tools'][-1]['function']['parameters']['properties'])

    def test_context_second_cycle_three_turns_and_frozen_cursor(self):
        self.save('🙂\r\n'*10000)
        a=self.agent
        calls=[]
        async def fake(**kwargs):
            calls.append(kwargs)
            if len(calls)==1:
                return reply([('memory_read_source',{'memory_id':'STATUS','view':'context'})])
            if len(calls)==2:
                cursor=a.last_p1_report['turns'][0]['tool_results'][0]['result']['next_cursor']
                return reply([('memory_read_source',{'memory_id':'STATUS','view':'context','cursor':cursor})])
            return reply()
        a.llm=NS(call=fake)
        result=asyncio.run(a.maintain([],cycle_id='read'))
        self.assertEqual(result['status'],'completed')
        self.assertEqual((len(calls),result['reads_used'],result['continuations_used']),(3,2,2))
        self.assertEqual([len(c['tools']) for c in calls],[6,6,5])
        for turn in result['turns'][:2]:
            self.assertEqual(turn['tool_results'][0]['result']['view'],'context')

    def test_missing_selected_event_does_not_block_bound_context(self):
        self.save()
        self.agent.links.state['events'].clear()
        self.assertEqual(self.read('sources')['status'],'source_missing')
        self.assertIn('A limit=50',''.join(p['text'] for p in self.collect('context')))

    def test_new_runtime_file_missing_or_changed_rejected(self):
        from pma_evidence_review.tools.run_p1_source_case import source_identity
        identity=source_identity(strict=False,candidate='source-links-context-v1')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in identity['source_files']:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes((ROOT/name).read_bytes())
            subprocess.run(['git','init','-q',str(root)],check=True)
            subprocess.run(['git','add','.'],cwd=root,check=True)
            subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                'commit','-qm','fixture'],cwd=root,check=True)
            self.assertEqual(source_identity(root=root,candidate='source-links-context-v1')['source_files'],
                identity['source_files'])
            path=root/next(n for n in identity['source_files'] if n.endswith('/p1_context_agent.py'))
            original=path.read_bytes();path.unlink()
            with self.assertRaises(RuntimeError):
                source_identity(root=root,candidate='source-links-context-v1')
            path.write_bytes(original+b'\n')
            with self.assertRaises(RuntimeError):
                source_identity(root=root,candidate='source-links-context-v1')

    def test_context_cursor_task_target_and_invalid_view_rejected(self):
        self.save('🙂'*20000)
        cursor=self.read()['next_cursor']
        self.assertIsNotNone(cursor)
        self.target['kind']='memory';self.target['id']=self.agent.memory.save_knowledge('other')
        state=self.agent.links.state
        state['refs'][self.target['id']]=deepcopy(state['refs']['STATUS'])
        state['refs'][self.target['id']].update(category='knowledge',content_sha256=digest('other'))
        self.target['ref']=deepcopy(state['refs'][self.target['id']])
        self.assertEqual(self.read(cursor=cursor)['status'],'invalid_cursor')
        self.assertEqual(self.read(view='anything')['status'],'invalid_tool_arguments')
        self.target={'kind':'status','id':'STATUS','ref':deepcopy(state['refs']['STATUS'])}
        path=self.agent.source_archive.window_path('c_r0')
        window=json.loads(path.read_text());window['task_id']='another'
        path.write_bytes(encode(window).encode('utf-8'));state['task_id']='another'
        self.agent.source_archive.task_id='another'
        state['refs']['STATUS']['context_sha256']=digest(encode(window))
        self.target['ref']=deepcopy(state['refs']['STATUS'])
        self.assertEqual(self.read(cursor=cursor)['status'],'invalid_cursor')

    def test_r1_r2_saves_recover_each_actual_continuation_prompt(self):
        self.responses.extend([
            reply([('memory_read_source',{'memory_id':'E1'})]),
            reply([('memory_save_knowledge',{'content':'saved at r1','source_ids':['E1']}),
                   ('memory_read_source',{'memory_id':'E1'})]),
            reply([('memory_save_knowledge',{'content':'saved at r2','source_ids':['E1']})])])
        result=asyncio.run(self.agent.maintain(
            [{'event_id':'continuation','observation':'receipt with 🙂\r\n'}],cycle_id='continuation'))
        self.assertEqual(result['status'],'completed')
        self.assertEqual(len(self.requests),3)
        self.assertEqual([len(r['tools']) for r in self.requests],[6,6,5])
        for round_index in (1,2):
            with self.subTest(round=round_index):
                row=next(r for r in self.agent._active_records().values()
                         if r.content==f'saved at r{round_index}')
                ref=self.agent.links.state['refs'][row.id]
                self.assertEqual(ref['context_window'],f'continuation_r{round_index}')
                self.target={'kind':'memory','id':row.id,'ref':deepcopy(ref)}
                context=''.join(p['text'] for p in self.collect('context'))
                actual=self.requests[round_index]['prompt']
                self.assertEqual(context,actual)
                self.assertNotEqual(context,self.requests[0]['prompt'])
                self.assertIn('## Previous P1 calls and receipts (historical data)',context)
                self.assertIn(encode(result['turns'][:round_index]),context)

    def test_valid_hash_does_not_override_window_identity_or_type(self):
        self.save()
        path=self.agent.source_archive.window_path('c_r0')
        original=json.loads(path.read_text())
        ref=self.agent.links.state['refs']['STATUS']
        for fault in ('cycle_id','archive_task','model_input'):
            with self.subTest(fault=fault):
                window=deepcopy(original)
                if fault=='cycle_id':
                    window['cycle_id']='different_cycle'
                elif fault=='model_input':
                    window['model_input']={'not':'a prompt string'}
                self.agent.source_archive.task='wrong task text' if fault=='archive_task' else 'task'
                raw=encode(window)
                path.write_bytes(raw.encode('utf-8'))
                ref['context_sha256']=digest(raw)
                self.target['ref']=deepcopy(ref)
                self.assertEqual(digest(path.read_bytes().decode('utf-8')),ref['context_sha256'])
                self.assertEqual(self.read()['status'],'source_binding_error')
        self.agent.source_archive.task='task'

    def test_real_shape_m2_source_context_delete_and_original_journal(self):
        key=self.agent.memory.save_knowledge('Correct fix')
        self.agent.source_archive.capture('legacy','legacy raw\r\n'*3000,[])
        state=deepcopy(self.agent.links.state)
        self.agent.links.bind_state(state,key,'knowledge','Correct fix',{
            'sources':[],'inherited_unassociated':[],'association':'legacy_unassociated'},'legacy')
        state['bank']=self.agent.memory.to_dict();self.agent.links.commit(state)
        self.responses.extend([
            reply([('memory_read_source',{'memory_id':'M2'})]),
            reply([('memory_read_source',{'memory_id':'M2','view':'context'})]),
            reply([('memory_delete',{'memory_id':'M2'}),
                   ('memory_update_status',{'content':'updated','source_ids':[]})])])
        result=asyncio.run(self.agent.maintain([],cycle_id='delete_shape'))
        self.assertEqual(result['status'],'completed')
        self.assertNotIn(key,self.agent._active_records())
        self.assertEqual(self.agent.memory.status,'updated')
        receipts=[t['tool_results'][0]['result'] for t in result['turns']]
        self.assertEqual([r['status'] for r in receipts],['source_unassociated','context_partial','applied'])
        self.assertEqual([receipts[0]['target'],receipts[1]['target'],receipts[2]['target_resolution']['resolved_memory_id']],[key]*3)
        self.assertEqual(result['turns'][2]['tool_calls'][0]['arguments'],{'memory_id':'M2'})
        self.assertEqual(result['operations'][0]['memory_id'],key)
        records=[json.loads(line) for line in (Path(self.temp.name)/'maintenance.jsonl').read_text().splitlines()]
        turn=next(r for r in records if r.get('kind')=='response_and_receipts' and r['window_id'].endswith('r2'))
        self.assertEqual(turn['tool_calls'][0]['arguments'],{'memory_id':'M2'})
        self.assertEqual(turn['tool_results'][0]['result']['target_resolution']['resolved_memory_id'],key)

    def test_alias_and_actual_id_share_resolution_reject_ambiguity_and_stale_targets(self):
        a=self.agent;key=a.memory.save_knowledge('victim')
        a._input('',0,[]);a.request_aliases=deepcopy(a.frozen_aliases)
        def apply(name,value):
            return a._apply({'name':name,'arguments':{'memory_id':value}},'unused',0,
                {'operations':[],'read_requests':0,'reads_used':0})
        for value in ('M2',key):
            self.assertEqual(apply('memory_read_source',value)['target'],key)
        # Actual ID collision with the alias must fail for both operations.
        a.memory.knowledge[0].id='M2'
        a._input('',0,[]);a.request_aliases=deepcopy(a.frozen_aliases)
        for name in ('memory_read_source','memory_delete'):
            self.assertEqual(apply(name,'M2')['status'],'ambiguous_memory_id')
        self.assertEqual(len(a.memory.knowledge),2)
        for value in ('E1','TASK','STATUS','unknown'):
            self.assertNotEqual(apply('memory_delete',value)['status'],'applied')
        # Fresh unambiguous snapshot supports actual ID deletion.
        a.memory.knowledge[0].id='keeper'
        a._input('',0,[]);a.request_aliases=deepcopy(a.frozen_aliases)
        a.memory.knowledge[1].content='changed'
        for name in ('memory_read_source','memory_delete'):
            self.assertEqual(apply(name,'M2')['status'],'memory_target_changed')
        a.memory.knowledge[1].content='victim'
        state=deepcopy(a.links.state);state['bank']=a.memory.to_dict();a.links.commit(state)
        self.assertEqual(apply('memory_delete',key)['status'],'applied')
        self.assertEqual(apply('memory_delete','M2')['status'],'entry_not_found')
        self.assertIn('keeper',a._active_records())

    def test_delete_binding_change_is_rejected_without_deleting(self):
        a=self.agent;key=next(iter(a._active_records()))
        a._input('',0,[]);a.request_aliases=deepcopy(a.frozen_aliases)
        a.links.state['refs'][key]={'changed':True}
        result=a._apply({'name':'memory_delete','arguments':{'memory_id':'M1'}},'unused',0,
            {'operations':[],'read_requests':0,'reads_used':0})
        self.assertEqual(result['status'],'memory_target_changed')
        self.assertIn(key,a._active_records())

    def test_invalid_tool_or_failed_delete_stops_remaining_batch_preserves_prior_commit(self):
        from unittest.mock import patch
        failures=[('memory_delete',{'memory_id':'missing'}),
                  ('unknown_tool',{}),('memory_delete',{'memory_id':4}),
                  ('memory_delete',{'memory_id':'M1'})]
        for index,bad in enumerate(failures):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as tmp:
                bank=GapMemory();keep=bank.save_knowledge('keep')
                async def fake(**kwargs):
                    return reply([('memory_save_gap',{'content':'committed before failure'}),bad,
                        ('memory_save_knowledge',{'content':'must not save'}),
                        ('memory_delete',{'memory_id':keep}),
                        ('memory_update_status',{'content':'must not update'})])
                a=ContextSourceP1Agent(task='t',task_id='t',memory=bank,llm=NS(call=fake),source_root=tmp)
                with patch.object(type(bank),'delete',return_value=False) if index==3 else patch.dict({},{}):
                    result=asyncio.run(a.maintain([],cycle_id='failure'))
                self.assertEqual(result['status'],'tool_error')
                self.assertEqual([r['result']['status'] for r in result['turns'][0]['tool_results']][2:],
                    ['not_executed_after_tool_failure']*3)
                self.assertIn(keep,a._active_records())
                self.assertEqual([r.content for r in a.gaps.entries],['committed before failure'])
                self.assertEqual(len(a.memory.knowledge),1)
                self.assertNotEqual(a.memory.status,'must not update')
                self.assertEqual(a.links.state['bank'],a.memory.to_dict())

    def test_recorded_a04_visible_calls_replay_deletes_exact_original_id(self):
        import hashlib
        from pma_evidence_review.tools.run_p1_source_case import build_case
        fixture_path=ROOT/'pma_evidence_review/fixtures/context_delete_a04_replay.json'
        fixture=json.loads(fixture_path.read_text(encoding='utf-8'))
        case_path=ROOT/'pma_evidence_review/p1_source_read_delivery/cases'/fixture['case_file']
        case=json.loads(case_path.read_text(encoding='utf-8'))
        case['source_manifest']=fixture['archived_source_manifest']
        self.assertEqual(hashlib.sha256(encode(case).encode()).hexdigest(),
                         fixture['archived_case_canonical_sha256'])
        recorded=deepcopy(fixture['turns']);requests=[]
        async def fake(**kwargs):
            requests.append(deepcopy(kwargs))
            return reply([(c['name'],c['arguments']) for c in recorded.pop(0)])
        with tempfile.TemporaryDirectory() as tmp:
            a=build_case(case,tmp,NS(call=fake),candidate='source-links-context-v1')
            self.assertIn('RL3HYG6d',a._active_records())
            result=asyncio.run(a.maintain(case['entries'],observation=case.get('observation'),
                step_count=case['step_count'],cycle_id='recorded_replay'))
            self.assertEqual(result['status'],'completed')
            self.assertEqual(len(requests),3)
            self.assertFalse(recorded)
            self.assertNotIn('RL3HYG6d',a._active_records())
            turns=result['turns']
            self.assertEqual([turns[i]['tool_results'][0]['result']['status'] for i in (0,1)],
                             ['source_unassociated','context_partial'])
            self.assertEqual([turns[i]['tool_results'][0]['result']['target'] for i in (0,1)],
                             ['RL3HYG6d']*2)
            self.assertEqual(turns[2]['tool_results'][0]['result']['target_resolution']['resolved_memory_id'],
                             'RL3HYG6d')
            self.assertEqual([r['result']['status'] for r in turns[2]['tool_results']],['applied']*6)
            for actual,expected in zip(turns,fixture['turns']):
                self.assertEqual([{'name':c['name'],'arguments':c['arguments']} for c in actual['tool_calls']],expected)
            self.assertEqual(a.links.state['bank'],a.memory.to_dict())
            self.assertEqual(a.memory.status,fixture['turns'][2][-1]['arguments']['content'])
            for turn in turns:
                for item in turn['tool_results']:
                    self.assertLessEqual(len(encode(item['result'])),8000)

    def test_repeated_delete_stops_batch_without_restoring_first_delete(self):
        key=next(iter(self.agent._active_records()))
        self.responses.append(reply([
            ('memory_delete',{'memory_id':'M1'}),('memory_delete',{'memory_id':'M1'}),
            ('memory_save_knowledge',{'content':'must not save'})]))
        result=asyncio.run(self.agent.maintain([],cycle_id='repeated_delete'))
        self.assertEqual(result['status'],'tool_error')
        self.assertNotIn(key,self.agent._active_records())
        self.assertEqual([r['result']['status'] for r in result['turns'][0]['tool_results']],
            ['applied','entry_not_found','not_executed_after_tool_failure'])
        self.assertEqual(self.agent.links.state['bank'],self.agent.memory.to_dict())

    def test_unavailable_context_remains_read_receipt_not_semantic_failure(self):
        self.responses.extend([
            reply([('memory_read_source',{'memory_id':'M1','view':'context'})]),
            reply([('memory_update_status',{'content':'still usable'})])])
        result=asyncio.run(self.agent.maintain([],cycle_id='unavailable'))
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['turns'][0]['tool_results'][0]['result']['status'],'context_unavailable')
        self.assertEqual(len(self.requests),2)
        self.assertEqual(self.agent.memory.status,'still usable')
