"""Offline scripted contracts for optional, unbounded generative P2 reads."""
import asyncio
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from pma_evidence_review.tests import test_p2_requirement_agent as selection
from pma_evidence_review.tests import test_p2_requirement_reminder as reminder
from pma_evidence_review.tests.test_bank_display import reply
from p2_requirement_reminder import SYSTEM


class UnboundedRetrievalTests(unittest.TestCase):
    setUp = selection.SelectionTests.setUp
    init = selection.SelectionTests.init
    save = selection.SelectionTests.save
    run_cycle = selection.SelectionTests.run_cycle
    files = selection.SelectionTests.files
    build = reminder.ReminderTests.build
    run_reminder = reminder.ReminderTests.run_reminder

    def history(self):
        return json.loads(self.p2_requests[-1]['prompt'].split(
            '## Visible P2 calls and receipts (historical data)\n', 1)[1])

    def test_five_sequential_reads_browse_source_history_then_generated_note(self):
        self.build()
        self.responses = [reply([self.save('child', selection.fixtures.FIXED)])]
        self.assertEqual(self.run_cycle('child', [{'event_id': 'c', 'observation': 'C raw'}])['status'], 'completed')
        self.p2.max_memory_in_prompt = 0
        before = self.files()

        def source(p2):
            rows = [json.loads(p['text']) for p in self.history()[-1]['tool_results'][0]['result']['parts']]
            alias = next(row['alias'] for row in rows if row['content'] == 'child')
            return reply([('memory_read_source', {'entry': alias})])

        def history(p2):
            page = self.history()[-1]['tool_results'][0]['result']
            handles = [json.loads(part['text']) for part in page['parts'] if part['field'] == 'input_memory']
            handle = next(row['history_handle'] for row in handles if row['content_preview'] == 'A earlier')
            return reply([('memory_read_source', {'entry': handle})])

        def fourth(p2):
            self.assertIn('A original raw', json.dumps(self.history()[-1]))
            self.assertIn('tools', self.p2_requests[-1])
            return reply([('memory_read_source', {'entry': 'TASK'})])

        def final(p2):
            self.assertEqual(len(self.history()), 5)
            self.assertTrue(all(request.get('tools') for request in self.p2_requests))
            self.assertNotIn('Tools closed.', self.p2_requests[-1]['prompt'])
            return reply(content='<context_for_action>A and C remain separate observations.</context_for_action>')

        self.p2_responses = [reply([('memory_browse', {})]), source, history, fourth,
                             reply([('memory_browse', {'view': 'all'})]), final]
        with patch('memory_agent.memory.universal_memory.UniversalMemory.search_knowledge', return_value=[]):
            result = self.run_reminder()
        self.assertEqual((result['status'], result['reads_used'], result['continuations_used'],
                          result['model_calls_attempted']), ('intervention', 5, 5, 6))
        self.assertTrue(result['should_inject'])
        self.assertEqual(result['delivery'], 'A and C remain separate observations.')
        self.assertEqual(self.files(), before)
        self.assertNotIn('Four shared reads', SYSTEM)
        self.assertNotIn('last turn has no tools', SYSTEM)

    def test_twenty_tool_rounds_then_one_tool_free_final_turn(self):
        self.build()
        before = self.files()
        note = 'Use the original task scope after reviewing the available evidence.'

        def read_again(p2):
            self.assertTrue(self.p2_requests[-1].get('tools'))
            self.assertNotIn(p2.final_turn_instruction, self.p2_requests[-1]['prompt'])
            self.assertFalse(p2.last_p2_report['limit_reached'])
            return reply([('memory_read_source', {'entry': 'TASK'})])

        def final(p2):
            self.assertEqual(len(self.p2_requests), 21)
            self.assertNotIn('tools', self.p2_requests[-1])
            self.assertTrue(all(request.get('tools') for request in self.p2_requests[:20]))
            prompt = self.p2_requests[-1]['prompt']
            self.assertTrue(prompt.endswith('\n' + p2.final_turn_instruction + '\n'))
            history_text = prompt.split(
                '## Visible P2 calls and receipts (historical data)\n', 1)[1]
            history, end = json.JSONDecoder().raw_decode(history_text)
            self.assertEqual(history_text[end:].strip(), p2.final_turn_instruction)
            self.assertEqual(len(history), 20)
            self.assertEqual(sum(len(turn['tool_results']) for turn in history), 20)
            self.assertTrue(p2.last_p2_report['limit_reached'])
            self.assertEqual(read.call_count, 20)
            return reply(content='<context_for_action>' + note + '</context_for_action>')

        self.p2_responses = [read_again] * 20 + [final]
        with patch.object(self.p2, '_read', wraps=self.p2._read) as read:
            result = self.run_reminder()
        self.assertEqual(read.call_count, 20)
        self.assertEqual((result['model_calls_attempted'], result['model_calls_completed'],
                          result['reads_used'], result['continuations_used']), (21, 21, 20, 20))
        self.assertTrue(result['limit_reached'])
        self.assertEqual((result['status'], result['should_inject'], result['delivery']),
                         ('intervention', True, note))
        self.assertEqual(len(result['turns']), 21)
        self.assertEqual(sum(len(turn['tool_results']) for turn in result['turns']), 20)
        self.assertEqual(result['turns'][-1]['tool_results'], [])
        self.assertEqual(self.p2_responses, [])
        self.assertEqual(self.files(), before)

    def test_record_not_yet_shown_is_visible_and_model_can_browse_then_retry(self):
        self.build()
        self.p2.max_memory_in_prompt = 0
        before = self.files()

        def recover(p2):
            self.assertEqual(self.history()[-1]['tool_results'][0]['result']['status'], 'record_not_yet_shown')
            self.assertNotIn('M1', p2.view.seen)
            return reply([('memory_browse', {})])

        def retry(p2):
            self.assertIn('M1', p2.view.seen)
            return reply([('memory_read_source', {'entry': 'M1'})])

        def final(p2):
            self.assertIn('A original raw', json.dumps(self.history()[-1]))
            return reply(content='<context_for_action>A remains scoped to the original receipt.</context_for_action>')

        self.p2_responses = [reply([('memory_read_source', {'entry': 'M1'})]), recover, retry, final]
        with patch('memory_agent.memory.universal_memory.UniversalMemory.search_knowledge', return_value=[]):
            result = self.run_reminder()
        self.assertEqual((result['status'], result['model_calls_completed']), ('intervention', 4))
        self.assertEqual(self.files(), before)

    def test_long_partial_record_pages_remain_available_until_fully_read(self):
        self.build()
        content = 'long record🙂\\\r\n' * 4000
        self.responses = [reply([self.save(content, selection.fixtures.FIXED)])]
        self.assertEqual(self.run_cycle('long')['status'], 'completed')
        self.p2.max_memory_in_prompt = 0
        parts = []
        state = {'alias': None, 'pages': 0}

        def page_or_finish(p2):
            page = self.history()[-1]['tool_results'][0]['result']
            state['pages'] += 1
            self.assertLess(state['pages'], 100, 'test fixture must reach a final page')
            parts.extend(part for part in page['parts'] if part['source_id'] == state['alias'])
            if page['next_cursor'] is not None:
                self.assertNotIn(state['alias'], p2.view.seen)
                self.p2_responses.append(page_or_finish)
                return reply([('memory_browse', {'cursor': page['next_cursor']})])
            self.assertIn(state['alias'], p2.view.seen)
            self.assertEqual(json.loads(''.join(part['text'] for part in parts))['content'], content)
            return reply(content='<context_for_action>The entire long record was available.</context_for_action>')

        def first(p2):
            state['alias'] = next(a for a, row in p2.view.aliases.items() if row.content == content)
            return reply([('memory_browse', {})])

        self.p2_responses = [first, page_or_finish]
        with patch('memory_agent.memory.universal_memory.UniversalMemory.search_knowledge', return_value=[]):
            result = self.run_reminder()
        self.assertEqual(result['status'], 'intervention')
        self.assertGreater(state['pages'], 4)
        self.assertEqual(result['reads_used'], state['pages'])
        self.assertTrue(all(request.get('tools') for request in self.p2_requests))

    def test_recoverable_model_tool_receipts_return_to_model(self):
        self.build()
        cases = [
            ('unknown_tool', 'unknown_tool', {}),
            ('invalid_tool_arguments', 'memory_browse', {'category': 7}),
            ('unknown_requirement', 'memory_browse', {'view': 'requirement', 'requirement': 'invented'}),
            ('invalid_cursor', 'memory_browse', {'cursor': 'not-a-cursor'}),
            ('source_not_in_snapshot_scope', 'memory_read_source', {'entry': 'M999'}),
        ]
        for expected, name, args in cases:
            with self.subTest(status=expected):
                self.p2_requests = []
                def recover(p2):
                    self.assertEqual(self.history()[-1]['tool_results'][0]['result']['status'], expected)
                    return reply(content='<no_intervention/>')
                self.p2_responses = [reply([(name, args)]), recover]
                result = self.run_reminder()
                self.assertEqual((result['status'], result['model_calls_completed']), ('no_intervention', 2))

    def test_malformed_native_arguments_recover_with_unique_missing_call_ids(self):
        self.build()
        malformed = NS(content='Inspect these entries.', tool_calls=[
            NS(function=NS(name='memory_browse', arguments='{broken')),
            NS(function=NS(name='memory_browse', arguments='{}')),
            NS(function=NS(name='memory_read_source', arguments='[not-json')),
            NS(function=NS(name='memory_read_source', arguments='{"entry":"TASK"}')),
        ])

        def recover(p2):
            turn = self.history()[-1]
            call_ids = [call['tool_call_id'] for call in turn['tool_calls']]
            receipt_ids = [row['tool_call_id'] for row in turn['tool_results']]
            self.assertEqual(len(call_ids), 4)
            self.assertEqual(len(set(call_ids)), 4)
            self.assertEqual(call_ids, receipt_ids)
            statuses = [row['result']['status'] for row in turn['tool_results']]
            self.assertEqual(statuses[0], 'invalid_tool_arguments')
            self.assertEqual(statuses[2], 'invalid_tool_arguments')
            self.assertEqual(statuses[1], 'browse_complete')
            self.assertNotIn(statuses[3], ('invalid_tool_arguments', 'not_executed_after_tool_failure'))
            self.assertIn('{broken', self.p2_requests[-1]['prompt'])
            self.assertIn('[not-json', self.p2_requests[-1]['prompt'])
            return reply(content='<context_for_action>Use the original task scope.</context_for_action>')

        self.p2_responses = [malformed, recover]
        result = self.run_reminder()
        self.assertEqual((result['status'], result['model_calls_completed'], result['reads_used']),
                         ('intervention', 2, 4))
        self.assertEqual(result['delivery'], 'Use the original task scope.')
        self.assertEqual(result['turns'][0]['response_tool_calls'][0]['arguments'], '{broken')
        self.assertTrue(result['should_inject'])

    def test_integrity_receipt_stops_batch_and_never_requests_another_turn(self):
        self.build()
        for status in ('source_binding_error', 'source_changed', 'entry_not_found'):
            with self.subTest(status=status):
                self.p2_requests = []
                self.p2_responses = [reply([('memory_read_source', {'entry': 'M1'}), ('memory_browse', {})]),
                                     reply(content='<context_for_action>Must never be delivered.</context_for_action>')]
                with patch.object(self.p2, '_read', return_value={'status': status}) as read:
                    result = self.run_reminder()
                self.assertEqual((result['status'], result['failure_kind']), ('tool_error', 'integrity'))
                self.assertEqual(read.call_count, 1)
                self.assertEqual(result['turns'][0]['tool_results'][1]['result']['status'], 'not_executed_after_tool_failure')
                self.assertEqual(result['model_calls_attempted'], 1)
                self.assertFalse(result['should_inject'])
                self.assertIsNone(result['delivery'])

    def test_legacy_selection_keeps_read_budget_final_turn_and_tool_error_abort(self):
        selection.SelectionTests.build(self)
        self.p2_responses = [reply([('memory_browse', {})] * 5), reply(content='<intervene>M1</intervene>')]
        result = asyncio.run(self.p2.select())
        self.assertEqual((result['status'], result['reads_used']), ('intervention', 4))
        self.assertEqual(result['turns'][0]['tool_results'][-1]['result']['status'], 'budget_exhausted')
        self.assertNotIn('tools', self.p2_requests[-1])
        self.assertEqual(json.loads(result['delivery'])['blocks'][0]['content'], 'A earlier')
        self.p2_responses = [reply([('unknown_tool', {})]), reply(content='<no_intervention/>')]
        result = asyncio.run(self.p2.select())
        self.assertEqual((result['status'], result['failure_kind'], result['model_calls_attempted']),
                         ('tool_error', 'model_tool', 1))


if __name__ == '__main__':
    unittest.main()
