"""Known GA patch fields are quoted text, not proof that a patch succeeded."""
import json
from pathlib import Path
import unittest

from evidence_gap_context import _project_tool_text
from gap_evidence import (RenderBlock, SourceRegistry, SourceScopeError,
                          bind_evidence, register_public_source,
                          render_source_blocks, sha256)
from graded_evidence_alignment import align_graded_evidence

FIXTURE = json.loads(Path(__file__).with_name('file_patch_public_fixture.json')
                     .read_text(encoding='utf-8'))


def project(raw, *, role='tool_command', projected=True):
    registry, blocks, parents = SourceRegistry('patch-projection'), [], {}
    identity = dict(source_id='public-command', order=15,
                    record_digest=sha256(raw), record_digest_kind='public_prompt_extract')

    def add(identity, role, text, path, **metadata):
        _, row = register_public_source(registry, event_id=identity['source_id'],
            role=role, text=text, order=identity['order'], field_path=path,
            record_digest=identity['record_digest'],
            record_digest_kind=identity['record_digest_kind'],
            parent_wrapper_source_id=parents.get(metadata.get('parent_field_path')),
            tool_call_id=metadata.get('tool_call_id'))
        parents[path] = row.source_id
        blocks.append(RenderBlock(registry.snapshot(row.source_id),
                                  metadata.get('render_spans')))

    if projected:
        _project_tool_text(add, identity, role, raw, 'commands/0')
    else:
        add(identity, role, raw, 'commands/0')
    return render_source_blocks(blocks, cycle_id='public-patch')


class FilePatchProjectionTests(unittest.TestCase):
    def test_actual_c8_c9_quotes_bind_decoded_new_content(self):
        source = FIXTURE['source']
        self.assertEqual(sha256(source['raw']), source['raw_sha256'])
        before, after = project(source['raw'], projected=False), project(source['raw'])
        for case in FIXTURE['cases']:
            with self.subTest(cycle=case['cycle_step']):
                quote = case['quote']
                self.assertEqual(align_graded_evidence([{'quote': quote}], before.catalog).status,
                                 'unbound')
                result = align_graded_evidence([{'quote': quote}], after.catalog)
                self.assertEqual(result.status, 'exact_unique')
                self.assertEqual(len(result.bound_refs), 1)
                ref = result.bound_refs[0]
                self.assertEqual([ref.start, ref.end], case['expected_interval'])
                visible = next(v for v in after.catalog.values()
                               if v.snapshot.record.source_id == ref.source_id)
                self.assertEqual(visible.snapshot.record.field_path, 'commands/0/args/new_content')
                self.assertEqual(visible.snapshot.blob.text[ref.start:ref.end], quote)
                self.assertEqual(visible.snapshot.record.role, 'tool_command')
                self.assertEqual(visible.snapshot.parent_wrapper.blob.text, source['raw'])
                self.assertEqual(visible.snapshot.record.tool_call_id,
                                 json.loads(source['raw'])['id'])

    def test_old_and_new_are_separate_and_parent_is_not_duplicate_body(self):
        old, new = 'before\nvalue', 'after\nvalue'
        raw = json.dumps(dict(tool_name='file_patch', id='patch-call',
            args=dict(path='x.txt', old_content=old, new_content=new, count=1)))
        parts = project(raw)
        self.assertEqual(len(parts.catalog), 3)
        for field, text in [('old_content', old), ('new_content', new)]:
            child = next(v for v in parts.catalog.values()
                         if v.snapshot.record.field_path.endswith('/' + field))
            self.assertEqual(child.snapshot.blob.text, text)
            self.assertEqual(child.snapshot.record.role, 'tool_command')
            self.assertEqual(child.snapshot.parent_wrapper.record.tool_call_id, 'patch-call')
            bind_evidence([dict(source=child.snapshot.record.handle, quote=text)], parts.catalog)
        self.assertIn('"path": "x.txt"', parts.text)
        parent = next(v for v in parts.catalog.values()
                      if v.snapshot.record.field_path == 'commands/0')
        with self.assertRaises(SourceScopeError):
            bind_evidence([dict(source=parent.snapshot.record.handle, quote=json.dumps(new))],
                          parts.catalog)

    def test_identical_old_and_new_remain_two_command_sources(self):
        body = 'same\ntext'
        raw = json.dumps(dict(tool_name='file_patch',
                              args=dict(old_content=body, new_content=body)))
        parts = project(raw)
        result = align_graded_evidence([{'quote': body}], parts.catalog)
        self.assertEqual(result.status, 'exact_multiple')
        self.assertEqual(len(result.bound_refs), 2)
        source_ids = {ref.source_id for ref in result.bound_refs}
        sources = [v.snapshot.record for v in parts.catalog.values()
                   if v.snapshot.record.source_id in source_ids]
        self.assertEqual({r.field_path for r in sources},
                         {'commands/0/args/old_content', 'commands/0/args/new_content'})
        self.assertEqual({r.role for r in sources}, {'tool_command'})

    def test_one_decode_only_preserves_literal_escapes_and_unicode(self):
        body = '雪 😀\n' + r'C:\new\test \n \t \u0041'
        raw = json.dumps(dict(tool_name='file_patch', args=dict(new_content=body)))
        parts = project(raw)
        child = next(v for v in parts.catalog.values()
                     if v.snapshot.record.field_path.endswith('/new_content'))
        self.assertEqual(child.snapshot.blob.text, body)
        self.assertIn(r'\u0041', child.snapshot.blob.text)
        self.assertEqual(align_graded_evidence([{'quote': body}], parts.catalog).status,
                         'exact_unique')

    def test_unknown_role_or_tool_and_nontext_fields_are_not_reinterpreted(self):
        for role, tool, fields in [
            ('tool_observation', 'file_patch', {'new_content': 'a\nb'}),
            ('agent_report', 'file_patch', {'new_content': 'a\nb'}),
            ('tool_command', 'unknown_patch', {'new_content': 'a\nb'}),
            ('tool_command', 'file_patch', {'old_content': None, 'new_content': 42}),
            ('tool_command', 'file_patch', {'old_content': '', 'new_content': ''}),
        ]:
            with self.subTest(role=role, tool=tool, fields=fields):
                raw = json.dumps(dict(tool_name=tool, args=fields))
                parts = project(raw, role=role)
                self.assertEqual(len(parts.catalog), 1)
                self.assertEqual(next(iter(parts.catalog.values())).snapshot.blob.text, raw)

    def test_malformed_and_nested_payloads_stay_literal(self):
        for raw in ['{"tool_name":"file_patch","args":{"new_content":"broken}',
                    '{"tool_name":"file_patch","args":{"new_content":"a","new_content":"b"}}',
                    json.dumps(dict(tool_name='file_patch', args={'edit': {'new_content': 'a\nb'}}))]:
            with self.subTest(raw=raw):
                parts = project(raw)
                self.assertEqual(len(parts.catalog), 1)
                self.assertEqual(next(iter(parts.catalog.values())).snapshot.blob.text, raw)


if __name__ == '__main__':
    unittest.main()
