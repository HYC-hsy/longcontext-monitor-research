"""Frozen P2 full-bank navigation, without model calls or persistent grants."""
import json
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from pma_evidence_review.tests import test_p1_requirements as fixtures
FIXED = fixtures.FIXED
from pma_evidence_review.tests.test_bank_display import reply
from p1_source_archive import encode
from p2_requirement_view import RequirementSelectionView


class ViewTests(unittest.TestCase):
    setUp = fixtures.RequirementTests.setUp
    init = fixtures.RequirementTests.init
    save = fixtures.RequirementTests.save
    run_cycle = fixtures.RequirementTests.run_cycle

    def seed(self):
        self.responses = [self.init(),reply([self.save('multi',FIXED),
            self.save('unclassified',[]),self.save('gap',[FIXED[1]],category='gap')])]
        self.assertEqual(self.run_cycle()['status'],'completed')
        return RequirementSelectionView(self.agent)

    def files(self):
        return {str(p.relative_to(self.temp.name)):p.read_bytes() for p in Path(self.temp.name).rglob('*') if p.is_file()}

    def test_full_groups_general_stable_aliases_and_no_files_changed(self):
        view = self.seed()
        before = self.files()
        all_page = view.browse()
        records = [json.loads(p['text']) for p in all_page['parts']]
        self.assertEqual(len(records),3)
        aliases = {r['content']:r['alias'] for r in records}
        for text in FIXED:
            page = view.browse(view='requirement',requirement=text)
            group = [json.loads(p['text']) for p in page['parts']]
            self.assertEqual(next(r['alias'] for r in group if r['content']=='multi'),aliases['multi'])
            self.assertEqual(next(r['alias'] for r in group if r['content']=='unclassified'),aliases['unclassified'])
            self.assertEqual(len({r['alias'] for r in group}),len(group))
        page = view.browse(view='requirement',requirement='General')
        self.assertEqual([json.loads(p['text'])['content'] for p in page['parts']],['unclassified'])
        self.assertEqual(json.loads(page['parts'][0]['text'])['requirements'],['General'])
        self.assertEqual(view.browse(view='unclassified')['status'],'invalid_tool_arguments')
        self.assertEqual(view.browse(view='requirement',requirement='new plan')['status'],'unknown_requirement')
        self.assertEqual(view.browse(view='all',requirement=FIXED[0])['status'],'invalid_tool_arguments')
        self.assertEqual(self.files(),before)

    def test_long_record_requires_full_lossless_return_before_selection_and_cursor_scope(self):
        fixed = [f'Preserve path {i}: C:' + ('\\a'*245) for i in range(4)]
        content = '正文🙂\r\n\\"'*5000
        self.responses = [self.init(fixed),reply([self.save(content,fixed)])]
        self.run_cycle()
        view = RequirementSelectionView(self.agent)
        page = view.browse()
        self.assertNotIn('M1',view.seen)
        self.assertEqual(view.read_source(memory_id='M1')['status'],'record_not_yet_shown')
        self.assertLessEqual(len(encode(page)),8000)
        self.assertIsNotNone(page['next_cursor'])
        self.assertEqual(view.browse(view='requirement',requirement='General',cursor=page['next_cursor'])['status'],'invalid_cursor')
        other = RequirementSelectionView(self.agent)
        self.assertEqual(other.browse(cursor=page['next_cursor'])['status'],'invalid_cursor')
        parts = page['parts'][:]
        for _ in range(100):
            page = view.browse(cursor=page['next_cursor'])
            self.assertLessEqual(len(encode(page)),8000)
            parts.extend(page['parts'])
            if page['next_cursor'] is None:
                break
        else:
            self.fail('unbounded browse paging')
        self.assertIn('M1',view.seen)
        record = json.loads(''.join(p['text'] for p in parts))
        self.assertEqual((record['content'],record['requirements']),(content,fixed))
        self.assertFalse(page['complete'])

    def test_sources_context_and_scoped_history_survive_delete_without_p1_writes(self):
        self.responses = [self.init(),reply([self.save('old A',[FIXED[0]])])]
        self.run_cycle('a',[{'event_id':'a','observation':'A raw receipt'}])
        old = self.agent.memory.knowledge[0].id
        self.responses = [reply([self.save('A+B',[FIXED[1]],('E1',)),('memory_delete',{'memory_id':'M1'})])]
        self.run_cycle('b',[{'event_id':'b','observation':'B raw receipt'}])
        view = RequirementSelectionView(self.agent)
        view.present(['M1'])
        before = self.files()
        page = view.read_source(memory_id='M1',view='sources')
        self.assertIn('B raw receipt',encode(page))
        self.assertNotIn('A raw receipt',encode(page))
        directory = [json.loads(p['text']) for p in page['parts'] if p['field']=='input_memory']
        handle = next(r['history_handle'] for r in directory if r['memory_id']==old)
        self.assertTrue(handle.startswith('P2H.'+view.id+'.'))
        history = view.read_source(memory_id=handle)
        self.assertIn('A raw receipt',encode(history))
        self.assertEqual(history['requirements'],[FIXED[0]])
        context = view.read_source(memory_id='M1',view='context')
        self.assertIn('old A',encode(context))
        other = RequirementSelectionView(self.agent)
        self.assertEqual(other.read_source(memory_id=handle)['status'],'source_not_in_snapshot_scope')
        raw = handle[len(view.history.prefix):]
        self.assertEqual(view.read_source(memory_id=raw)['status'],'source_not_in_snapshot_scope')
        self.assertEqual(view.read_source(memory_id=view.history.prefix+'H1.'+'0'*64)['status'],'invalid_history_handle')
        self.assertEqual(self.files(),before)

    def test_freeze_rejects_uncommitted_bank_and_selected_ref_or_task_changes(self):
        view = self.seed()
        view.present(['M1'])
        self.assertTrue(view.selection_valid(self.agent,['M1']))
        key = view.aliases['M1'].id
        self.agent.links.state['refs'][key]['association'] = 'changed'
        self.assertFalse(view.selection_valid(self.agent,['M1']))
        # Source reads retain the frozen ref rather than silently following that mutation.
        self.assertNotEqual(view.links.state['refs'][key]['association'],'changed')
        self.agent.memory.save_knowledge('uncommitted')
        with self.assertRaisesRegex((ValueError,RuntimeError),'uncommitted|p1_state_not_reconciled'):
            RequirementSelectionView(self.agent)
        self.agent.task = 'another task'
        self.assertFalse(view.selection_valid(self.agent,['TASK']))

    def test_optional_source_long_pages_missing_context_and_independent_valid_sources(self):
        raw = 'original raw🙂\r\n\\"'*5000
        self.responses = [self.init(),reply([self.save('summary',[FIXED[0]])])]
        self.run_cycle('long',[{'event_id':'long','observation':raw}])
        view = RequirementSelectionView(self.agent)
        view.present(['M1'])
        before = self.files()
        page = view.read_source(memory_id='M1',view='sources')
        self.assertIsNotNone(page['next_cursor'])
        self.assertEqual(view.read_source(memory_id='M1',view='context',cursor=page['next_cursor'])['status'],'invalid_cursor')
        parts = page['parts'][:]
        for _ in range(100):
            self.assertLessEqual(len(encode(page)),8000)
            if page['next_cursor'] is None:
                break
            page = view.read_source(memory_id='M1',view='sources',cursor=page['next_cursor'])
            parts.extend(page['parts'])
        else:
            self.fail('unbounded source paging')
        self.assertEqual(''.join(p['text'] for p in parts if p['field']=='observation'),raw)
        self.assertEqual(self.files(),before)
        # A missing context cannot hide independently intact selected source fields.
        self.agent.source_archive.window_path('long_r0').unlink()
        page = view.read_source(memory_id='M1',view='sources')
        self.assertEqual(page['input_memory_coverage'],'unavailable')
        self.assertIn('original raw',encode(page))
        page = view.read_source(memory_id='M1',view='context')
        self.assertEqual(page['status'],'context_missing')
        self.assertFalse(page['page_sequence_complete'])
        self.assertFalse(page['complete'])

    def test_unassociated_source_fallback_is_context_and_missing_is_never_complete(self):
        self.responses = [self.init(),reply([self.save('no association',[],())])]
        self.run_cycle('unassociated')
        view = RequirementSelectionView(self.agent)
        view.present(['M1'])
        page = view.read_source(memory_id='M1')
        self.assertEqual((page['requested_view'],page['resolved_view']),('auto','context'))
        self.agent.source_archive.window_path('unassociated_r0').unlink()
        missing = view.read_source(memory_id='M1')
        self.assertEqual(missing['status'],'context_missing')
        self.assertFalse(missing['complete'])
        self.assertFalse(missing['page_sequence_complete'])

    def test_p1_instance_writer_instrumentation_is_not_copied_into_p2(self):
        self.seed()
        self.responses = [reply([self.save('child',FIXED)])]
        self.run_cycle('child')
        before = self.files()
        with patch.object(self.agent.links,'commit',side_effect=AssertionError('no P1 writes')) as writer:
            view = RequirementSelectionView(self.agent)
            alias = next(a for a,r in view.aliases.items() if r.content=='child')
            view.present([alias])
            page = view.read_source(memory_id=alias)
            self.assertTrue(any(p['field']=='input_memory' for p in page['parts']))
            self.assertTrue(any(token.startswith(view.history.prefix) for token in view.links.state['history_grants']))
            writer.assert_not_called()
        self.assertEqual(self.files(),before)

    def test_alias_and_displayed_internal_id_resolve_one_record_without_hidden_access(self):
        view = self.seed()
        row = view.aliases['M1']
        self.assertEqual(view.read_source(memory_id=row.id)['status'],'record_not_yet_shown')
        view.present(['M1'])
        a = view.read_source(memory_id='M1',view='sources')
        b = view.read_source(memory_id=row.id,view='sources')
        self.assertEqual(a,b)
        self.assertEqual(a['target'],row.id)
        self.assertEqual(view.read_source(memory_id='nonexistent')['status'],'source_not_in_snapshot_scope')

    def test_alias_internal_id_collision_is_rejected_without_double_resolution(self):
        self.seed()
        # First source-ordered object has internal ID M2; a later one is aliased M2.
        first = next(r for r in self.agent.memory.knowledge if r.content=='multi')
        second = next(r for r in self.agent.memory.knowledge if r.content=='unclassified')
        old,other = first.id,second.id
        first.id,second.id = 'M2','X'
        state = deepcopy(self.agent.links.state)
        state['refs']['M2'] = state['refs'].pop(old)
        state['refs']['X'] = state['refs'].pop(other)
        state['bank'] = self.agent.memory.to_dict()
        self.agent.links.commit(state)
        view = RequirementSelectionView(self.agent)
        view.present(list(view.aliases))
        self.assertEqual(view.aliases['M1'].id,'M2')
        self.assertEqual(view.read_source(memory_id='M2')['status'],'ambiguous_memory_id')
        self.assertEqual(view.read_source(memory_id='M1')['target'],'M2')
        self.assertEqual(view.read_source(memory_id='M2',alias_only=True)['target'],'X')
        self.assertEqual(view.read_source(memory_id='M1',alias_only=True)['target'],'M2')
        self.assertEqual(view.read_source(memory_id='X',alias_only=True)['status'],'source_not_in_snapshot_scope')
        self.assertEqual(view.read_source(memory_id='X')['target'],'X')

    def test_browse_condition_misuse_and_same_filter_cursor_contract(self):
        self.responses = [self.init(),reply([self.save('long🙂'*6000,[FIXED[0]])])]
        self.run_cycle()
        view = RequirementSelectionView(self.agent)
        for args in ({'view':'requirement'},{'view':'all','requirement':FIXED[0]},
                     {'view':'unclassified','requirement':FIXED[0]},{'category':'gaps'}):
            self.assertEqual(view.browse(**args)['status'],'invalid_tool_arguments')
        page = view.browse(view='requirement',requirement=FIXED[0],category='knowledge')
        self.assertIsNotNone(page['next_cursor'])
        self.assertEqual(view.browse(view='requirement',requirement=FIXED[0],category='gap',
            cursor=page['next_cursor'])['status'],'invalid_cursor')
        continued = view.browse(view='requirement',requirement=FIXED[0],category='knowledge',cursor=page['next_cursor'])
        self.assertNotEqual(continued['status'],'invalid_cursor')

    def test_model_browse_pages_hide_internal_ids_without_changing_host_records(self):
        self.responses = [self.init(),reply([self.save('long🙂'*6000,[FIXED[0]])])]
        self.run_cycle()
        view = RequirementSelectionView(self.agent)
        page = view.browse(model_view=True)
        self.assertEqual(view.browse(cursor=page['next_cursor'])['status'],'invalid_cursor')
        parts = page['parts'][:]
        while page['next_cursor']:
            page = view.browse(model_view=True,cursor=page['next_cursor'])
            self.assertLessEqual(len(encode(page)),8000)
            parts.extend(page['parts'])
        row = json.loads(''.join(p['text'] for p in parts))
        self.assertEqual(row['alias'],'M1')
        self.assertNotIn('memory_id',row)
        self.assertEqual(row['content'],'long🙂'*6000)
        self.assertIn('memory_id',view.record('M1'))
        grouped = view.browse(view='requirement',requirement=FIXED[0],model_view=True)
        self.assertEqual(grouped['parts'][0]['source_id'],'M1')



if __name__=='__main__':
    unittest.main()
