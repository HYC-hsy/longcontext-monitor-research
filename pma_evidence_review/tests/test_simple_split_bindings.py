"""Exact alternative origins are eligible only in v3; no semantic inference."""
from copy import deepcopy
import json
import unittest

from pma_evidence_review import citation_inputs as ci
from pma_evidence_review.inputs import digest
from pma_evidence_review.tests.test_citation_inputs import aligned
from pma_evidence_review.tests.no_network import install_guard


def multiple():
    parent, rows = aligned()
    op = parent['operations'][0]
    alignment = rows[op['revision_id']]
    data = json.loads(alignment['alignment_json'])
    source = deepcopy(parent['sources'][2])
    source.update(source_id=json.dumps(['ns', 'public', 'command', 'commands/0']),
                  role='tool_command', field_path='commands/0', event_order=1)
    parent['sources'].append(source)
    ref = deepcopy(data['bound_refs'][0])
    ref.update(source_id=source['source_id'], role=source['role'], order=1)
    data['bound_refs'].append(ref)
    data['items'][0]['candidates'].append(ref)
    data['items'][0]['status'] = data['status'] = alignment['status'] = 'exact_multiple'
    alignment['alignment_json'] = json.dumps(data)
    return op, alignment, parent, data


class SimpleBindingTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def prepare(self, op, alignment, parent, data):
        alignment['alignment_json'] = json.dumps(data)
        return ci.prepare(op, alignment, parent, allow_multiple=True)

    def test_multiple_origins_opt_in_only_and_keep_both_roles(self):
        op, alignment, parent, data = multiple()
        self.assertEqual(ci.prepare(op, alignment, parent)['status'], 'citation_set_not_eligible')
        result = self.prepare(op, alignment, parent, data)
        self.assertEqual(result['status'], 'ready')
        candidates = result['citations'][0]['candidates']
        self.assertEqual([row['reference']['role'] for row in candidates],
                         ['tool_observation', 'tool_command'])
        self.assertEqual([row['original_excerpt'] for row in candidates], ['green', 'green'])

    def test_missing_quote_not_guessed(self):
        op, alignment, parent, data = multiple()
        data['bound_refs'] = data['items'][0]['candidates'] = []
        data['status'] = data['items'][0]['status'] = alignment['status'] = 'unbound'
        data['items'][0]['quote'] = 'not visible'
        result = self.prepare(op, alignment, parent, data)
        self.assertEqual(result['status'], 'citation_set_not_eligible')
        self.assertEqual(result['citations'][0]['candidates'], [])
        self.assertIn('citation_0:binding_unbound', result['issues'])

    def test_integrity_and_cardinality_still_fail_closed(self):
        for mutation in ('duplicate', 'missing', 'tamper', 'normalized', 'wrong_aggregate'):
            with self.subTest(mutation=mutation):
                op, alignment, parent, data = multiple()
                item = data['items'][0]
                if mutation == 'duplicate':
                    item['candidates'][1] = deepcopy(item['candidates'][0])
                elif mutation == 'missing':
                    item['candidates'].pop()
                elif mutation == 'tamper':
                    item['candidates'][1]['snippet_sha256'] = digest('bad')
                elif mutation == 'normalized':
                    item['status'] = data['status'] = alignment['status'] = 'normalized_multiple'
                else:
                    alignment['status'] = 'exact_unique'
                self.assertEqual(self.prepare(op, alignment, parent, data)['status'],
                                 'citation_set_not_eligible')


if __name__ == '__main__':
    unittest.main()
