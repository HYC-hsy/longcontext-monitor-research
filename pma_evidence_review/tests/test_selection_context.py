"""Deterministic P2 information-preservation checks; no model calls."""
import copy
import json
from pathlib import Path
import sys
import unittest

STAGE = Path(__file__).resolve().parents[2] / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
sys.path.insert(0, str(STAGE))
from selection_context import digest, project_steps, render_selection
from tag_selection_contract import Item, Snapshot, dispatch

ANCHOR = '\n### [WORKING MEMORY]\n<history>\nold\n</history>\nCurrent turn: 3\n\n<key_info>old state</key_info>'


class SelectionContextTests(unittest.TestCase):
    def test_tools_are_opaque_and_ordered(self):
        commands = [json.dumps({'id': str(i), 'tool_name': 'asset_process',
                    'args': {'nested': [{'data': ANCHOR}], 'index': i}}) for i in range(7)]
        results = [{'tool_use_id': str(i), 'content': json.dumps({
            'status': 'timeout' if i == 6 else 'error', 'exit_code': 5,
            'stdout': ANCHOR * 100, 'stderr': '<history>literal</history>'})}
                   for i in range(7)]
        entries = [{'step': 4, 'commands': commands, 'analysis': 'visible response',
                    '_evidence_identity': {'source_id': 'e7', 'order': 7},
                    'observation': json.dumps({'content': ANCHOR + '\n[MASTER] new rule',
                                               'tool_results': results})}]
        before = copy.deepcopy(entries)
        rows, audit = project_steps(entries)
        self.assertEqual(entries, before)
        self.assertEqual(rows[0]['commands'], commands)
        self.assertEqual(rows[0]['observation']['tool_results'], results)
        self.assertEqual(rows[0]['_evidence_identity'], entries[0]['_evidence_identity'])
        self.assertEqual(rows[0]['observation']['content'], '\nCurrent turn: 3\n\n[MASTER] new rule')
        self.assertEqual(len(audit['removed']), 1)
        self.assertEqual(audit['retained_unknown'], [])
        self.assertEqual(rows[0]['latest_framework_checkpoint_not_selectable'], '\n<key_info>old state</key_info>')

    def test_unknown_and_ambiguous_wrappers_are_preserved(self):
        for content in ('<history>not a host wrapper</history>', ANCHOR.replace('old\n', '<history>nested</history>\n')):
            entry = {'step': 1, 'observation': json.dumps({'content': content, 'tool_results': []})}
            rows, audit = project_steps([entry])
            self.assertEqual(rows, [entry])
            self.assertEqual(len(audit['retained_unknown']), 1)
        rows, audit = project_steps([{'observation': '{malformed'}])
        self.assertEqual(rows, [{'observation': '{malformed'}])
        self.assertEqual(project_steps([])[0], [])

    def test_latest_available_earlier_context_and_unicode(self):
        earlier = '<earlier_context>\n保留画面及\n旧约束\n</earlier_context>\n'
        entries = [{'step': i, 'observation': json.dumps({'content': content, 'tool_results': []})}
                   for i, content in enumerate([ANCHOR.replace('<history>', earlier + '<history>'), ANCHOR])]
        rows, audit = project_steps(entries)
        self.assertEqual(rows[0]['latest_earlier_context_not_selectable'], earlier)
        self.assertNotIn('latest_earlier_context_not_selectable', rows[1])
        prompt = render_selection([], '', rows, 2)
        self.assertIn('保留画面', prompt)
        self.assertEqual(json.JSONDecoder().raw_decode(prompt.split('## Recent visible steps (not selectable)\n')[1])[0], rows)

    def test_catalogue_and_protocol_bindings(self):
        task = 'Render the complete layered animation.\n'
        item = Item('stable-id', 'revision-8', 'knowledge', 'Keep alpha channel.')
        snapshot = Snapshot('call', 'cycle', 'version', task, (item,))
        args = dict(completion_call_id='call', active_cycle='cycle',
                    active_task_version='version', active_records={item.id: item})
        outcome = dispatch('<intervene>TASK,M1</intervene>', snapshot, **args)
        self.assertEqual([b['content'] for b in outcome.blocks], [task, item.content])
        self.assertEqual(outcome.blocks[1]['revision'], item.revision)
        self.assertEqual(dispatch('<no_intervention/>', snapshot, **args).kind, 'no_intervention')
        args['active_records'] = {}
        self.assertEqual(dispatch('<intervene>M1</intervene>', snapshot, **args).kind, 'error')
        catalogue = [{'alias': 'TASK', 'content': task}, {'alias': 'M1', 'content': item.content}]
        prompt = render_selection(catalogue, 'internal', [], 1)
        self.assertLess(prompt.index('Selectable catalogue'), prompt.index('Current internal status'))
        self.assertEqual(prompt.count(json.dumps(task)), 1)
        self.assertEqual(prompt.count(item.content), 1)

    def test_production_preparation_uses_same_window(self):
        from pma_evidence_review.tests.runtime_boundary_support import wrapper
        from evidence_gap_context import prepare_context
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            actor, calls = wrapper(Path(directory))
            gate = actor._memory_agent
            actor._task_description = gate.task = 'Render animation.\n'
            actor._evidence_task_identity = {'source_id': 'task', 'order': 1, 'record_digest': 'task'}
            actor._accumulated_observations = [{'step': 1}]
            for step in range(2, 12):
                actor._accumulated_observations.append({'step': step, 'analysis': 'public',
                    'commands': ['command-' + str(step)], 'plan': None,
                    '_evidence_identity': {'source_id': str(step), 'order': step, 'record_digest': str(step)},
                    'observation': json.dumps({'content': ANCHOR, 'tool_results': []})})
            before = copy.deepcopy(actor._accumulated_observations)
            prepare_context(actor)
            prompt = gate._build_phase2_prompt(actor._get_memory_agent_context(), 11)
            steps = json.JSONDecoder().raw_decode(prompt.split('## Recent visible steps (not selectable)\n')[1])[0]
            self.assertEqual([row['step'] for row in steps], list(range(4, 12)))
            self.assertEqual(sum('latest_framework_checkpoint_not_selectable' in row for row in steps), 1)
            self.assertEqual(actor._accumulated_observations, before)
            self.assertIn('binding not recorded', prompt)
            self.assertEqual(calls, [])

    def test_synthetic_long_window_preserves_all_data(self):
        task = 'Render eight animation frames with transparent backgrounds.\n'
        catalogue = [{'alias': 'TASK', 'content': task},
                     {'alias': 'M1', 'category': 'knowledge', 'content': 'Keep frame order.',
                      'binding': 'binding_status=unbound; NOT semantic proof'}]
        earlier = '<earlier_context>\nUse the approved palette.\n</earlier_context>\n'
        entries = []
        for step in range(1, 9):
            command = json.dumps({'id': f'render-{step}', 'tool_name': 'frame_renderer',
                                  'args': {'frame': step, 'layers': ['background', 'sprite']}})
            stdout = ('像素验证结果\n[WORKING MEMORY]<history>literal asset data</history>\n' * 200)
            result = {'tool_use_id': f'render-{step}', 'content': json.dumps({
                'status': 'timeout' if step == 8 else 'success', 'stdout': stdout,
                'stderr': 'synthetic renderer deadline' if step == 8 else '',
                'exit_code': 124 if step == 8 else 0})}
            content = ANCHOR.replace('<history>', earlier + '<history>')
            entries.append({'step': step, 'analysis': f'Render frame {step}.',
                            'commands': [command], 'observation': json.dumps({
                                'content': content, 'tool_results': [result]})})
        frozen = copy.deepcopy(entries)
        rows, audit = project_steps(entries)
        prompt = render_selection(catalogue, 'Rendering in progress.', rows, 8)
        self.assertEqual(entries, frozen)
        self.assertEqual(audit['input_sha256'], digest(json.dumps(entries, ensure_ascii=True, sort_keys=True)))
        self.assertEqual(len(audit['removed']), 8)
        self.assertEqual(audit['retained_unknown'], [])
        self.assertEqual(len(rows), 8)
        for old, new in zip(entries, rows):
            self.assertEqual(old['analysis'], new['analysis'])
            self.assertEqual(old['commands'], new['commands'])
            self.assertEqual(json.loads(old['observation'])['tool_results'], new['observation']['tool_results'])
        self.assertEqual(rows[-1]['latest_earlier_context_not_selectable'], earlier)
        self.assertEqual(sum('latest_framework_checkpoint_not_selectable' in row for row in rows), 1)
        self.assertEqual(sum('latest_earlier_context_not_selectable' in row for row in rows), 1)
        decoded = json.JSONDecoder().raw_decode(prompt.split('## Selectable catalogue\n')[1])[0]
        self.assertEqual(decoded, catalogue)
        self.assertIn('binding_status=unbound', prompt)
        self.assertGreater(len(prompt), 100000)  # Real tool data is never shortened to meet a target.


if __name__ == '__main__':
    unittest.main()
