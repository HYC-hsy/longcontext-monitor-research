"""Offline topic/General contract; scripted calls are not model quality evidence."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace as NS
import unittest

from pma_evidence_review.tests import test_p1_requirements as fixtures
from pma_evidence_review.tests.test_bank_display import reply
from p1_requirements import assignment, topics
from p1_source_archive import encode
from p2_requirement_agent import RequirementSelectionAgent
from p2_requirement_reminder import RequirementReminderAgent
from p2_requirement_view import RequirementSelectionView


class TopicGeneralTests(unittest.TestCase):
    setUp = fixtures.RequirementTests.setUp
    init = fixtures.RequirementTests.init
    save = fixtures.RequirementTests.save
    run_cycle = fixtures.RequirementTests.run_cycle
    reopen = fixtures.RequirementTests.reopen

    def seed(self, long=False):
        self.bodies = {'specific': 'specific', 'other': 'other', 'general': 'general',
                       'both': 'both' + ('🙂\\"\r\n' * 4500 if long else ''),
                       'gap': 'general gap'}
        a, b = fixtures.FIXED
        self.responses = [self.init(), reply([
            self.save(self.bodies['specific'], [a]),
            self.save(self.bodies['other'], [b]),
            self.save(self.bodies['general'], []),
            self.save(self.bodies['both'], [a, b]),
            self.save(self.bodies['gap'], [], category='gap'),
        ])]
        self.assertEqual(self.run_cycle()['status'], 'completed')
        return RequirementSelectionView(self.agent)

    def read_all(self, reader, **filters):
        chunks, order = {}, []
        cursor = None
        for _ in range(100):
            page = reader.browse(cursor=cursor, **filters)
            self.assertIn(page['status'], ('browse_partial', 'browse_complete'))
            self.assertLessEqual(len(encode(page)), 8000)
            for part in page['parts']:
                alias = part['source_id']
                if alias not in chunks:
                    chunks[alias] = []
                    order.append(alias)
                chunks[alias].append(part['text'])
            cursor = page['next_cursor']
            if cursor is None:
                return [json.loads(''.join(chunks[a])) for a in order], page
        self.fail('browse pagination did not terminate')

    def test_empty_assignment_falls_back_and_catalog_stays_task_derived(self):
        self.assertEqual(assignment([], fixtures.FIXED), [])
        self.assertEqual(assignment([], []), [])
        self.assertEqual(topics(fixtures.FIXED), fixtures.FIXED)
        self.seed()
        self.assertEqual(self.agent.requirement_state.data['catalog'], fixtures.FIXED)
        self.reopen()
        record = next(r for r in self.agent.export_view()['records'] if r['content'] == 'general')
        self.assertEqual(record['requirements'], [])

    def test_empty_catalog_can_save_and_browse_general(self):
        self.responses = [self.init([]), reply([self.save('still useful', [])])]
        self.assertEqual(self.run_cycle()['status'], 'completed')
        rows, _ = self.read_all(RequirementSelectionView(self.agent), view='all')
        self.assertEqual([r['content'] for r in rows], ['still useful'])
        self.assertNotIn('requirements', rows[0])

    def test_topic_union_deduplicates_before_pagination_and_preserves_order(self):
        view = self.seed(long=True)
        expected = [a for a in view.aliases if fixtures.FIXED[0] in view.attributes[a]['requirements']]
        rows, page = self.read_all(view, view='requirement', requirement=fixtures.FIXED[0])
        self.assertEqual([r['alias'] for r in rows], expected)
        self.assertEqual(len(rows), 2)
        self.assertEqual(page['matching_record_count'], 2)
        self.assertEqual(sum(r['content'] == self.bodies['both'] for r in rows), 1)
        self.assertTrue(set(expected) <= view.seen)

    def test_no_general_query_and_category_intersection(self):
        view = self.seed()
        self.assertEqual(view.browse(view='requirement', requirement='General')['status'], 'unknown_requirement')
        rows, page = self.read_all(view, view='all', category='gap')
        self.assertEqual([r['content'] for r in rows], ['general gap'])
        self.assertNotIn('requirements', rows[0])
        self.assertEqual(page['matching_category_counts'], {'knowledge': 0, 'procedural': 0, 'gap': 1})
        self.assertEqual(view.browse(view='requirement', requirement='invented')['status'], 'unknown_requirement')

    def test_partial_union_record_not_granted_and_cursor_scoped(self):
        view = self.seed(long=True)
        alias = next(a for a, r in view.aliases.items() if r.content == self.bodies['both'])
        page = view.browse(view='requirement', requirement=fixtures.FIXED[0])
        self.assertIsNotNone(page['next_cursor'])
        self.assertNotIn(alias, view.seen)
        self.assertEqual(view.read_source(memory_id=alias)['status'], 'record_not_yet_shown')
        for filters in ({'view': 'requirement', 'requirement': fixtures.FIXED[1]},
                        {'view': 'requirement', 'requirement': fixtures.FIXED[0], 'category': 'knowledge'},
                        {'view': 'all'}):
            self.assertEqual(view.browse(cursor=page['next_cursor'], **filters)['status'], 'invalid_cursor')

    def test_initial_records_have_own_topics_without_fixed_topic_directory(self):
        self.seed()
        for cls in (RequirementSelectionAgent, RequirementReminderAgent):
            requests = []
            async def fake(**kwargs):
                requests.append(deepcopy(kwargs))
                return reply(content='<no_intervention/>')
            p2 = cls(p1=self.agent, llm=NS(call=fake))
            report = asyncio.run(p2.select(observation='current observation', step_count=2))
            self.assertEqual(report['status'], 'no_intervention')
            prompt = requests[0]['prompt']
            self.assertNotIn('## Fixed requirements and initial memberships', prompt)
            marker = ('## Original task and shown memory (data)\n' if cls is RequirementReminderAgent
                      else '## Selectable catalogue\n')
            rows = json.loads(prompt.split(marker, 1)[1].split('\n', 1)[0])[1:]
            self.assertEqual(len(rows), len(p2.view.aliases))
            for row in rows:
                expected = p2.view.attributes[row['alias']]['requirements']
                if expected:
                    self.assertEqual(row['requirements'], expected)
                else:
                    self.assertNotIn('requirements', row)
            browse = p2.tools()[0]['function']
            self.assertEqual(browse['parameters']['properties']['view']['enum'], ['all', 'requirement'])
            self.assertNotIn('General', browse['description'])


if __name__ == '__main__':
    unittest.main()

