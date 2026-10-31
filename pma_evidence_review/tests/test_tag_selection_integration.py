"""Focused phase-2 tag protocol and host delivery checks (no model)."""
import asyncio
from dataclasses import replace
import json
import unittest

from pma_evidence_review.tests import test_verbatim_selection_integration as helper_tests
from tag_selection_contract import (Item, Snapshot, dispatch, delivery_json,
    diagnostic, parse_output)


class TagContractTests(unittest.TestCase):
    def setUp(self):
        self.item = Item('native-gap', 'rev-1', 'gap', ' 条件\r\n原文\ud800')
        self.snapshot = Snapshot('call-1', 'cycle-1', 'task-v1', '完整任务\n', (self.item,))
        self.live = {self.item.id: self.item}

    def decide(self, raw, **changes):
        options = {'completion_call_id': 'call-1', 'active_cycle': 'cycle-1',
                   'active_task_version': 'task-v1', 'active_records': self.live}
        options.update(changes)
        return dispatch(raw, self.snapshot, **options)

    def test_bare_fenced_and_exact_unicode_delivery(self):
        for raw in ('<intervene>M1,TASK</intervene>',
                    '  ```xml\n<intervene>M1,TASK</intervene>\n```  ',
                    '```text\n<intervene>M1,TASK</intervene>\n```',
                    '```\n<intervene>M1,TASK</intervene>\n```'):
            result = self.decide(raw)
            self.assertEqual(result.kind, 'intervention')
            wire = delivery_json(result).encode('utf-8')
            self.assertEqual([b['content'] for b in json.loads(wire)['blocks']],
                             [self.item.content, self.snapshot.task])
            self.assertEqual(diagnostic(result)['raw_output'], raw)
        self.assertTrue(self.decide('  <no_intervention/>  ').normalized)
        self.assertIsNone(delivery_json(self.decide('<no_intervention/>')))

    def test_invalid_tags_never_partially_deliver(self):
        invalid = ('<intervene></intervene>', '<intervene>M1,M1</intervene>',
                   '<intervene>M2</intervene>', '<intervene>STATUS</intervene>',
                   '<intervene>M 1</intervene>', '<intervene M="1">M1</intervene>',
                   '<intervene><x>M1</x></intervene>',
                   '<intervene>M1</intervene><no_intervention/>',
                   'reason <intervene>M1</intervene>', '{"decision":"intervene"}',
                   '```json\n<intervene>M1</intervene>\n```',
                   '```xml\n<intervene>M1</intervene>',
                   '```\n<intervene>M1</intervene>\n``` extra', None)
        for raw in invalid:
            with self.subTest(raw=raw):
                result = self.decide(raw)
                self.assertEqual(result.kind, 'error')
                self.assertIsNone(delivery_json(result))

    def test_stale_and_wrong_call_never_deliver(self):
        for changes in ({'completion_call_id': 'call-2'},
                        {'active_cycle': 'cycle-2'},
                        {'active_task_version': 'task-v2'},
                        {'active_records': {self.item.id: replace(self.item, content='new')}},
                        {'active_records': {}}):
            with self.subTest(changes=changes):
                self.assertEqual(self.decide('<intervene>M1</intervene>', **changes).kind,
                                 'error')
        self.assertEqual(self.decide('<intervene>TASK</intervene>',
                         active_records={}).kind, 'intervention')

    def test_nonstring_response_diagnostic_is_safe(self):
        class Unsafe:
            def __repr__(self):
                raise AssertionError('repr used')
        result = self.decide(Unsafe())
        self.assertEqual(result.error, 'output_not_string')
        self.assertEqual(diagnostic(result)['raw_output'], {'invalid_type': 'Unsafe'})


class TagHostTests(unittest.TestCase):
    def setUp(self):
        self.helper = helper_tests.VerbatimSelectionIntegrationTests()

    def test_two_calls_alias_reuse_is_bound_to_each_snapshot(self):
        bank = helper_tests.LatestEvidenceGapMemory()
        first = bank.save_gap('first gap')
        bank._revision(first, receipt_id='commit-1')
        agent, _ = self.helper._agent(lambda a: '<intervene>M1</intervene>', bank=bank)
        agent.prepare_visible_context('visible', [])
        first_result = asyncio.run(agent.process('visible', 1))
        self.assertEqual(json.loads(first_result.context_for_action)['blocks'][0]['content'],
                         'first gap')
        bank.delete_gap(first)
        second = bank.save_gap('second gap')
        bank._revision(second, receipt_id='commit-2')
        agent.prepare_visible_context('visible again', [])
        second_result = asyncio.run(agent.process('visible again', 2))
        self.assertEqual(json.loads(second_result.context_for_action)['blocks'][0]['content'],
                         'second gap')
        self.assertNotEqual(first_result.context_for_action, second_result.context_for_action)

    def test_malformed_response_is_not_no_intervention(self):
        agent, _ = self.helper._agent(lambda a: '```json\n<no_intervention/>\n```')
        agent.prepare_visible_context('visible', [])
        result = asyncio.run(agent.process('visible', 1))
        self.assertFalse(result.should_inject)
        self.assertEqual(agent.last_gap_report['selection_error']['status'],
                         'selection_error')
        self.assertNotIn('selection', agent.last_gap_report)


if __name__ == '__main__':
    unittest.main()
