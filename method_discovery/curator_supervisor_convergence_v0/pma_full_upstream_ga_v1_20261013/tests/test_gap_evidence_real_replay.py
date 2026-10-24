"""Offline public-log development replay, not online/model effectiveness evidence."""
from collections import Counter
import importlib.util
import json
from pathlib import Path
import unittest

from evidence_gap_context import _project_tool_text
from gap_evidence import (RenderBlock, SourceRegistry, SourceScopeError, bind_evidence,
                          excerpt, register_public_source, render_source_blocks, sha256)

ARTIFACT = Path(__file__).resolve().parents[1] / 'evidence_interface_repair_v1_offline'
FIXTURE = json.loads((ARTIFACT / 'real_public_fixture.json').read_text(encoding="utf-8"))


def render(source, projected):
    registry, blocks, parents = SourceRegistry('real-public-development-replay'), [], {}
    identity = dict(source_id=source['old_handle'], order=source['order'],
                    record_digest=source['raw_sha256'], record_digest_kind='public_prompt_extract')

    def add(identity, role, text, path, **meta):
        _, row = register_public_source(registry, event_id=identity['source_id'], role=role,
            text=text, order=identity['order'], field_path=path,
            record_digest=identity['record_digest'], record_digest_kind=identity['record_digest_kind'],
            parent_wrapper_source_id=parents.get(meta.get('parent_field_path')),
            tool_call_id=meta.get('tool_call_id'))
        parents[path] = row.source_id
        blocks.append(RenderBlock(registry.snapshot(row.source_id), meta.get('render_spans')))

    if projected:
        _project_tool_text(add, identity, source['role'], source['raw'], source['field_path'])
    else:
        add(identity, source['role'], source['raw'], source['field_path'])
    return render_source_blocks(blocks, cycle_id='offline-public-replay')


def check(parts, path, quote):
    visible = next(v for v in parts.catalog.values() if v.snapshot.record.field_path == path)
    try:
        refs = bind_evidence([dict(source=visible.snapshot.record.handle, quote=quote)], parts.catalog)
        assert excerpt(refs[0], {visible.visibility_ref: visible}) == quote
        return 'accepted', visible
    except SourceScopeError as error:
        return error.code, visible


def replay():
    rows = []
    for case in FIXTURE['cases']:
        source = FIXTURE['sources'][case['source_key']]
        assert sha256(source['raw']) == source['raw_sha256']
        before, _ = check(render(source, False), source['field_path'], case['quote'])
        projected = render(source, True)
        after, child = check(projected, case['child_path'], case['quote'])
        # A corrected field selection is necessary. Parent wrapper no longer
        # renders the JSON string body, so its old citation is not repaired.
        unchanged_parent, _ = check(projected, source['field_path'], case['quote'])
        parent = child.snapshot.parent_wrapper
        assert parent is not None and parent.blob.text == source['raw']
        assert child.snapshot.record.parent_wrapper_source_id == parent.record.source_id
        rows.append(dict(case_id=case['case_id'], expected=case['expected'],
            original_source_handle=source['old_handle'], old_format_result=before,
            mapped_child_path=case['child_path'], replay_child_handle=child.snapshot.record.handle,
            projected_mapped_result=after, projected_parent_result=unchanged_parent,
            quote_sha256=sha256(case['quote']), raw_parent_sha256=source['raw_sha256']))
    return rows


class RealPublicReplayTests(unittest.TestCase):
    def test_fixture_matches_archived_public_sources(self):
        spec = importlib.util.spec_from_file_location('real_replay_extract', ARTIFACT / 'extract_real_replay.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.extract(), FIXTURE)

    def test_actual_failed_references_under_explicit_field_mapping(self):
        rows = replay()
        self.assertEqual(Counter(r['expected'] for r in rows),
                         dict(decoded_unique=26, ambiguous=3, noncontiguous=2, wrong_source=1))
        for row in rows:
            with self.subTest(case=row['case_id']):
                self.assertEqual(row['old_format_result'],
                    'ambiguous_quote' if row['expected'] == 'ambiguous' else 'quote_not_visible')
                self.assertEqual(row['projected_mapped_result'],
                    'accepted' if row['expected'] == 'decoded_unique' else
                    'ambiguous_quote' if row['expected'] == 'ambiguous' else 'quote_not_visible')
                self.assertEqual(row['projected_parent_result'], 'quote_not_visible')

    def test_real_rejections_are_not_escape_failures(self):
        for case in FIXTURE['cases']:
            raw = FIXTURE['sources'][case['source_key']]['raw']
            if case['expected'] == 'noncontiguous':
                body = json.loads(raw)['stdout']
                self.assertNotIn(case['quote'], body)
                cursor = 0
                for line in case['quote'].splitlines():
                    position = body.find(line, cursor)
                    self.assertGreaterEqual(position, cursor)
                    cursor = position + len(line)
            elif case['expected'] == 'wrong_source':
                witness = case['wrong_source_witness']
                self.assertEqual(sha256(witness['raw']), witness['raw_sha256'])
                self.assertNotEqual(witness['old_handle'],
                                    FIXTURE['sources'][case['source_key']]['old_handle'])
                self.assertNotIn(case['quote'], json.loads(raw)['stdout'])
                self.assertIn(case['quote'], json.loads(witness['raw'])['stdout'])

    def test_actual_quotes_cover_control_characters_and_html_code(self):
        cases = FIXTURE['cases']
        self.assertTrue(any('\r\n' in c['quote'] for c in cases))
        self.assertTrue(any('\n' in c['quote'] for c in cases))
        self.assertTrue(any('"' in c['quote'] for c in cases))
        html = next(c for c in cases if c['case_id'].startswith('html-'))
        self.assertIn('class JSRemovalParser(HTMLParser):', html['quote'])
        self.assertTrue(html['child_path'].endswith('/args/content'))


if __name__ == '__main__':
    unittest.main()
