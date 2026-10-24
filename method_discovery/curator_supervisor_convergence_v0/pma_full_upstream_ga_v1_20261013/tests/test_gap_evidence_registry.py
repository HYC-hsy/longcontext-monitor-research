"""Deterministic stdlib checks of the production registry and literal binder."""
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gap_evidence as ge


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = ge.SourceRegistry("run/task")

    def source(self, text="alpha β\r\n😀", **changes):
        args = dict(event_id="event-1", role="agent_report", text=text, order=1,
                    field_path="response", record_digest=ge.sha256("accepted"),
                    record_digest_kind="accepted_public_envelope")
        args.update(changes)
        _, record = ge.register_public_source(self.registry, **args)
        return self.registry.snapshot(record.source_id)

    def render(self, snapshot, spans=None):
        return ge.render_source_blocks([ge.RenderBlock(snapshot, spans)], cycle_id="cycle-1")

    def bind(self, rendered, source, quote):
        return ge.bind_evidence([dict(source=source.record.handle, quote=quote)], rendered.catalog)

    def test_identity_repeat_and_full_change_rejection(self):
        first = self.source()
        self.assertIs(self.source(), first)
        for changes in ({"text": "other"}, {"role": "tool_observation"}, {"order": 2},
                        {"record_digest": "1" * 64}, {"record_digest_kind": "raw_record"}):
            with self.subTest(changes=changes), self.assertRaises(ge.SourceScopeError):
                self.source(**changes)
        self.assertIs(self.registry.snapshot(first.record.source_id), first)

    def test_namespaced_fields_and_blob_dedup(self):
        first = self.source()
        second = self.source(event_id="event-2")
        third = self.source(field_path="other")
        self.assertEqual(len({s.record.source_id for s in (first, second, third)}), 3)
        self.assertIs(first.blob, second.blob)
        with self.assertRaises(FrozenInstanceError):
            first.record.role = "tool_observation"
        with self.assertRaises(TypeError):
            self.registry.sources["fake"] = first

    def test_handle_collision_and_invalid_identity(self):
        first = self.source()
        self.registry._handles["s" + ge.sha256(ge._key("run/task", "public", "new", "response"))[:12]] = first.record.source_id
        with self.assertRaisesRegex(ge.SourceScopeError, "collision"):
            self.source(event_id="new")
        for changes in ({"role": "analysis"}, {"order": True}, {"order": -1},
                        {"record_digest": "z" * 64}, {"text": ""}, {"field_path": ""}):
            with self.subTest(changes=changes), self.assertRaises(ge.SourceScopeError):
                self.source(**changes)

    def test_unicode_exactness_and_ref_tampering(self):
        source = self.source()
        rendered = self.render(source)
        ref, = self.bind(rendered, source, "β\r\n😀")
        resolver = {v.visibility_ref: v for v in rendered.catalog.values()}
        self.assertEqual((ref.start, ref.end, ref.role), (6, 10, "agent_report"))
        self.assertEqual(ge.excerpt(ref, resolver), "β\r\n😀")
        for changes in ({"start": True}, {"end": 100}, {"role": "tool_observation"},
                        {"order": True}, {"source_text_sha256": "0" * 64},
                        {"snippet_sha256": "0" * 64}, {"source_kind": "memory"},
                        {"visibility_ref": "other"}, {"parent_revision_id": "fake"}):
            self.assertFalse(ge.bound_ref_valid(replace(ref, **changes), resolver))
        visible = resolver[ref.visibility_ref]
        self.assertFalse(ge.bound_ref_valid(ref, {ref.visibility_ref: replace(visible, visible_spans=((0, 10), (0, 10)))}))
        for quote in ("β\n😀", "Β", " β\r\n😀 "):
            with self.assertRaises(ge.SourceScopeError):
                self.bind(rendered, source, quote)

    def test_strict_evidence_and_overlap(self):
        source = self.source("aaa")
        rendered = self.render(source)
        for evidence in (None, [], (), [{"source": source.record.handle, "quote": ""}],
                         [{"source": "hidden", "quote": "a"}],
                         [{"source": source.record.handle, "quote": "aa"}],
                         [{"source": [], "quote": "aaa"}],
                         [{"source": source.record.handle, "quote": "aaa", "role": "agent_report"}]):
            with self.subTest(evidence=evidence), self.assertRaises(ge.SourceScopeError):
                ge.bind_evidence(evidence, rendered.catalog)

    def test_visible_spans_no_bridging_or_duplicate_occurrence(self):
        source = self.source("one hidden two")
        rendered = self.render(source, ((0, 3), (11, 14), (0, 3)))
        self.assertEqual(len(self.bind(rendered, source, "one")), 1)
        for quote in ("hidden", "one hidden two"):
            with self.assertRaises(ge.SourceScopeError):
                self.bind(rendered, source, quote)
        other = self.source("hidden leaf", event_id="unused")
        with self.assertRaises(ge.SourceScopeError):
            self.bind(rendered, other, "hidden leaf")

    def test_multi_source_dedup_and_frozen_catalog(self):
        a, b = self.source("first"), self.source("second", event_id="second")
        rendered = ge.render_source_blocks([ge.RenderBlock(a), ge.RenderBlock(b)],
                                          cycle_id="c", prefix="P", suffix="S")
        items = [{"source": s.record.handle, "quote": s.blob.text} for s in (a, b, a)]
        self.assertEqual(len(ge.bind_evidence(items, rendered.catalog)), 2)
        self.source("new", event_id="later")
        self.assertEqual(len(rendered.catalog), 2)
        self.assertEqual(rendered.manifest.request_sha256, ge.sha256(rendered.text))
        self.assertNotIn("first", json.dumps(ge.record_to_dict(rendered.manifest)))
        with self.assertRaises(TypeError):
            rendered.catalog["fake"] = None

    def test_memory_source_stays_derived_and_parented(self):
        _, row = ge.register_memory_source(self.registry, revision_id="revision-old", text="old claim")
        source = self.registry.snapshot(row.source_id)
        rendered = self.render(source)
        ref, = self.bind(rendered, source, "old claim")
        self.assertEqual((ref.source_kind, ref.role, ref.parent_revision_id),
                         ("memory", "memory_derived", "revision-old"))
        self.assertEqual(rendered.manifest.pre_cycle_revision_refs, ("revision-old",))
        resolver = {v.visibility_ref: v for v in rendered.catalog.values()}
        self.assertFalse(ge.bound_ref_valid(replace(ref, source_kind="public"), resolver))

    def test_raw_wrapper_and_decoded_child_are_distinct(self):
        wrapper = self.source('{"stdout":"hello\\nworld"}', role="tool_observation", field_path="result")
        child = self.source("hello\nworld", role="tool_observation", field_path="result/stdout",
                            parent_wrapper_source_id=wrapper.record.source_id)
        rendered = self.render(wrapper)
        self.bind(rendered, wrapper, "hello\\nworld")
        for source, quote in ((child, "hello\nworld"), (wrapper, "hello\nworld")):
            with self.assertRaises(ge.SourceScopeError):
                self.bind(rendered, source, quote)
        self.bind(self.render(child), child, "hello\nworld")
        with self.assertRaises(ge.SourceScopeError):
            self.source("wrong", role="tool_observation", field_path="result/stderr",
                        parent_wrapper_source_id=wrapper.record.source_id)

    def test_catalog_span_input_is_detached(self):
        source = self.source("one hidden two")
        spans = [[0, 3]]
        rendered = self.render(source, spans)
        spans[0][1] = 14
        self.assertEqual(next(iter(rendered.catalog.values())).visible_spans, ((0, 3),))
        with self.assertRaises(ge.SourceScopeError):
            self.bind(rendered, source, "hidden")

    def test_duplicate_blocks_keep_manifest_alignment(self):
        source = self.source("once")
        rendered = ge.render_source_blocks([ge.RenderBlock(source)] * 2, cycle_id="repeat")
        self.assertEqual(len(self.bind(rendered, source, "once")), 1)
        self.assertEqual(len(rendered.manifest.ordered_source_refs), 2)
        self.assertEqual(len(rendered.manifest.visibility_refs), 2)

    def test_reference_only_receipt_and_shared_chunks(self):
        source = self.source("long text " * 100)
        rendered = self.render(source)
        refs = self.bind(rendered, source, source.blob.text)
        receipt = ge.Receipt("receipt-1", "run", "cycle", 0, "save", "revision", refs)
        prior = ge.append_chunk(None, [receipt])
        later = ge.append_chunk(prior, [receipt])
        self.assertIs(later.previous, prior)
        self.assertIs(ge.append_chunk(later, []), later)
        self.assertNotIn(source.blob.text, json.dumps(ge.record_to_dict(receipt)))
        self.assertIs(rendered.catalog[source.record.handle].snapshot, source)


if __name__ == "__main__":
    unittest.main()
