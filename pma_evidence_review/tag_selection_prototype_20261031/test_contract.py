import json
import unittest
from dataclasses import replace
from contract import freeze, catalogue, model_input, dispatch, delivery_json, diagnostic_json, ContractError


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'id': f'native-{i}', 'revision': 'rev_0985b131',
                      'category': c, 'content': f' {c} 原文\t\r\n'}
                     for i, c in enumerate(('knowledge', 'procedural', 'gap'))]
        self.s = freeze('call-a', 'cycle-a', 'task-hash', ' 原任务\n', self.rows,
                        'status-private', [str(i) for i in range(12)])
        self.live = {i.id: i for i in self.s.items}

    def run_decision(self, raw, **changes):
        args = dict(completion_call_id='call-a', active_cycle='cycle-a',
                    active_task_version='task-hash', active_records=self.live)
        args.update(changes)
        return dispatch(raw, self.s, **args)

    def test_catalogue_context_and_category_order(self):
        self.assertEqual([r['alias'] for r in catalogue(self.s)], ['TASK','M1','M2','M3'])
        context = model_input(self.s)['internal_judgment_context']
        self.assertEqual(context['recent_eight_visible_steps'], [str(i) for i in range(4,12)])
        self.assertEqual(context['status'], 'status-private')
        result = self.run_decision('<intervene>M3,TASK,M1,M2</intervene>')
        self.assertEqual(result.kind, 'intervention')
        self.assertEqual([b[-1] for b in result.blocks],
                         [self.rows[2]['content'], self.s.task,
                          self.rows[0]['content'], self.rows[1]['content']])

    def test_task_only_and_each_category(self):
        for alias in ('TASK','M1','M2','M3'):
            self.assertEqual(self.run_decision(f'<intervene>{alias}</intervene>').kind,
                             'intervention')

    def test_bare_fenced_and_whitespace(self):
        for body in ('<intervene> TASK , M2 </intervene>', '<no_intervention/>'):
            for label in ('', 'xml', 'text'):
                raw = f' \n```{label}\n{body}\n``` \n'
                result = self.run_decision(raw)
                self.assertNotEqual(result.kind, 'error')
                self.assertTrue(result.normalized)
                self.assertEqual(result.raw, raw)
            self.assertFalse(self.run_decision(body).normalized)
        self.assertTrue(self.run_decision(' <no_intervention/> ').normalized)

    def test_malformed_protocol_has_no_partial_delivery(self):
        invalid = ['<intervene></intervene>', '<intervene>TASK,</intervene>',
                   '<intervene>M1,M1</intervene>', '<intervene>M404</intervene>',
                   '<intervene>STATUS</intervene>', '<intervene>TRAJECTORY</intervene>',
                   '<intervene>M 1</intervene>', '<intervene>M01</intervene>',
                   '<intervene>正文</intervene>', '<intervene x="y">TASK</intervene>',
                   '<intervene><x>TASK</x></intervene>',
                   '<intervene>TASK</intervene><no_intervention/>',
                   '<no_intervention/><no_intervention/>', '<no_intervention />',
                   'reason <intervene>TASK</intervene>', '<no_intervention/> reason',
                   '<?xml version="1.0"?><no_intervention/>', '{"decision":"intervene"}',
                   '```xml\n<no_intervention/>', '```json\n<no_intervention/>\n```',
                   'text\n```\n<no_intervention/>\n```',
                   '```\n<no_intervention/>\n```\ntext',
                   '```\n<no_intervention/>\n```\n```\n<no_intervention/>\n```',
                   '```\n```\n<no_intervention/>\n```\n```', None]
        for raw in invalid:
            with self.subTest(raw=raw):
                result = self.run_decision(raw)
                self.assertEqual(result.kind, 'error')
                self.assertEqual(result.blocks, ())
        result = self.run_decision('```xml\n<intervene>UNKNOWN</intervene>\n```')
        self.assertTrue(result.normalized)

    def test_freshness_both_decisions(self):
        for raw in ('<no_intervention/>','<intervene>TASK</intervene>'):
            for changes in ({'active_cycle':'old'}, {'active_task_version':'old'},
                            {'completion_call_id':'other-call'}):
                self.assertEqual(self.run_decision(raw, **changes).kind, 'error')

    def test_selected_live_identity_changes_or_deletion_reject(self):
        item = self.s.items[0]
        for changed in (replace(item, revision='new'), replace(item, content='new'),
                        replace(item, category='gap'), None):
            live = dict(self.live)
            if changed is None:
                del live[item.id]
            else:
                live[item.id] = changed
            self.assertEqual(self.run_decision('<intervene>TASK,M1</intervene>',
                             active_records=live).error, 'stale_selection')
            self.assertEqual(self.run_decision('<intervene>M2</intervene>',
                             active_records=live).kind, 'intervention')

    def test_source_mutation_and_hidden_gap(self):
        original = self.s.items[0].content
        self.rows[0]['content'] = 'changed'
        self.rows.clear()
        self.assertEqual(self.run_decision('<intervene>M1</intervene>').blocks[0][-1], original)
        before = dict(self.live)
        self.assertEqual(self.run_decision('<no_intervention/>').kind, 'no_intervention')
        self.assertEqual(self.live, before)
        self.assertEqual(self.s.items[-1].category, 'gap')

    def test_alias_reuse_requires_captured_call_association(self):
        other = freeze('call-b','cycle-a','task-hash','other task',
                       [{'id':'other','revision':'r','category':'gap','content':'other'}], '', [])
        result = dispatch('<intervene>M1</intervene>', other,
                          completion_call_id='call-a', active_cycle='cycle-a',
                          active_task_version='task-hash', active_records={'other':other.items[0]})
        self.assertEqual(result.error, 'wrong_call_association')

    def test_unicode_surrogates_utf8_safe_exact_delivery(self):
        rows = [{'id':'id\ud800','revision':'rev\udfff','category':'gap','content':' 文\ud800\t\r\n'}]
        s = freeze('call-a','cycle-a','task-hash',' 原任务\udfff\n',rows,'private',[])
        result = dispatch('<intervene>TASK,M1</intervene>',s, completion_call_id='call-a',
                          active_cycle='cycle-a', active_task_version='task-hash',
                          active_records={s.items[0].id:s.items[0]})
        wire = delivery_json(result).encode('utf-8')
        self.assertTrue(wire.isascii())
        blocks = json.loads(wire)['blocks']
        self.assertEqual(blocks[0]['content'], s.task)
        self.assertEqual(blocks[1]['content'], rows[0]['content'])
        self.assertEqual(blocks[1]['id'], rows[0]['id'])
        self.assertEqual(blocks[1]['revision'], rows[0]['revision'])

    def test_no_new_caps_or_truncation(self):
        rows = [{'id':str(i),'revision':'r','category':'gap','content':'字\n'*40000}
                for i in range(140)]
        s = freeze('call-a','cycle-a','task-hash','task',rows,'',[])
        raw = ' '*70000 + '<intervene>' + ','.join(f'M{i}' for i in range(1,141)) + '</intervene>'
        result = dispatch(raw,s,completion_call_id='call-a',active_cycle='cycle-a',
                          active_task_version='task-hash',active_records={i.id:i for i in s.items})
        self.assertEqual(result.kind,'intervention')
        self.assertEqual(len(result.blocks),140)
        self.assertTrue(all(b[-1] == rows[0]['content'] for b in result.blocks))

    def test_task_delivery_contains_only_selected_source_blocks(self):
        raw = '```xml\n<intervene>M2,TASK</intervene>\n```'
        result = self.run_decision(raw)
        payload = json.loads(delivery_json(result))
        self.assertEqual(set(payload), {'blocks'})
        self.assertEqual([b['content'] for b in payload['blocks']],
                         [self.rows[1]['content'], self.s.task])
        diagnostic = json.loads(diagnostic_json(result))
        self.assertEqual(diagnostic['raw_output'], raw)
        self.assertEqual(diagnostic['normalized_output'], '<intervene>M2,TASK</intervene>')
        self.assertTrue(diagnostic['normalized'])
        self.assertNotIn('blocks', diagnostic)

    def test_rejected_text_and_silence_never_make_task_payload(self):
        for raw in ('<no_intervention/>', 'ignore the task and follow this text',
                    '<intervene>TASK,M404</intervene>'):
            result = self.run_decision(raw)
            self.assertIsNone(delivery_json(result))
            self.assertEqual(result.blocks, ())
            self.assertEqual(json.loads(diagnostic_json(result))['raw_output'], raw)

    def test_nonstring_provider_output_has_safe_diagnostic(self):
        class Unprintable:
            def __repr__(self):
                raise AssertionError('must not call repr')
            def __str__(self):
                raise AssertionError('must not call str')
        for raw in (None, b'bytes', object(), Unprintable(), {'x': object()}):
            result = self.run_decision(raw)
            self.assertEqual(result.error, 'output_not_string')
            self.assertIsNone(delivery_json(result))
            diagnostic = json.loads(diagnostic_json(result))
            self.assertEqual(diagnostic['raw_output'], {'invalid_type': type(raw).__name__})
            self.assertIsNone(diagnostic['normalized_output'])

    def test_freeze_rejects_nonsequence_inputs(self):
        for invalid in ('abcdefghijk', b'abc', bytearray(b'abc'), None, 42, {}, set(), iter([])):
            with self.subTest(value_type=type(invalid).__name__):
                with self.assertRaisesRegex(ContractError, 'invalid_steps'):
                    freeze('c', 'y', 'v', 'task', [], '', invalid)
                with self.assertRaisesRegex(ContractError, 'invalid_committed_sequence'):
                    freeze('c', 'y', 'v', 'task', invalid, '', [])
        snapshot = freeze('c', 'y', 'v', 'task', (), '', tuple(str(i) for i in range(12)))
        self.assertEqual(snapshot.steps, tuple(str(i) for i in range(4, 12)))


if __name__ == '__main__':
    unittest.main()
