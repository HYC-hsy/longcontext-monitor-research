"""Offline source and type contract controls; no model transport is imported."""

import hashlib
import unittest

from .schema import validate_snapshot
from .source import (ContractError, SourceCatalog, canonical, strict_loads,
                     validate_leaf)


def leaf(text, *, source_id="u0", source_kind="user_requirement"):
    return {"source_id": source_id, "event_id": "initial", "field_path": "text",
            "source_kind": source_kind, "ga_turn": 0, "event_seq": 0,
            "truncated": False, "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def empty_snapshot():
    return {"schema_version": "stateful-proactive-memory/1", "task_id": "task",
            "episode_id": "episode", "state_version": 0, "committed_event_seq": 0,
            "B": {"G": {"task_version": 1,
                        "original_user_sources": [{"source_id": "u0", "start": 0,
                                                   "end": 4, "quote": "task"}],
                        "specifications": [], "goal_deltas": []},
                  "W": {"entities": [], "states": [], "relations": []},
                  "DeltaE": [], "DeltaA": [], "F": None}}


class ContractTests(unittest.TestCase):
    def test_strict_json(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '[1.2]'):
            with self.assertRaises(ContractError):
                strict_loads(raw)
        self.assertEqual(strict_loads('{"字":"x"}'), {"字": "x"})
        self.assertEqual(canonical({"b": 2, "a": 1}), b'{"a":1,"b":2}')

    def test_source_exact_unicode_and_visibility(self):
        source = leaf("a😀a", source_id="tool", source_kind="tool_result")
        validate_leaf(source)
        catalog = SourceCatalog({"tool": source}, "window-1")
        span = catalog.add("tool", 1, 2, "support")
        self.assertEqual(catalog.resolve({"evidence_id": span.evidence_id,
                         "quote": "😀"}, purpose="support",
                         allowed_kinds={"tool_result"})["start"], 1)
        with self.assertRaises(ContractError):
            catalog.resolve({"evidence_id": span.evidence_id, "quote": "😀"},
                            purpose="closure")
        with self.assertRaises(ContractError):
            catalog.resolve({"evidence_id": span.evidence_id, "quote": "a"},
                            purpose="support")

    def test_snapshot_no_entity_fact_bypass(self):
        source = leaf("task")
        snapshot = empty_snapshot()
        validate_snapshot(snapshot, {"u0": source})
        snapshot["B"]["W"]["entities"].append({"entity_id": "e", "entity_type":
            "file", "display_name": "file", "installed": True})
        with self.assertRaises(ContractError):
            validate_snapshot(snapshot, {"u0": source})

    def test_overlapping_quote_ambiguity_and_exact_stored_ref(self):
        source = leaf("aaa", source_id="t", source_kind="tool_result")
        catalog = SourceCatalog({"t": source}, "window")
        context = catalog.add("t", 0, 3, "audit")
        with self.assertRaisesRegex(ContractError, "ambiguous_quote"):
            catalog.resolve({"evidence_id": context.evidence_id, "quote": "aa"},
                            purpose="audit", allowed_kinds={"tool_result"})
        exact = catalog.add("t", 0, 2, "audit", exact_stored_ref=True)
        self.assertEqual(catalog.resolve({"evidence_id": exact.evidence_id,
            "quote": "aa"}, purpose="audit")["end"], 2)
        with self.assertRaisesRegex(ContractError, "quote_mismatch"):
            catalog.resolve({"evidence_id": exact.evidence_id, "quote": "a"},
                            purpose="audit")

    def test_cached_literal_never_bypasses_role_or_current_visibility(self):
        source = leaf("observed", source_id="t", source_kind="tool_result")
        first = SourceCatalog({"t": source}, "window-1")
        span = first.add("t", 0, 8, "audit")
        wire = {"evidence_id": span.evidence_id, "quote": "observed"}
        first.resolve(wire, purpose="audit", allowed_kinds={"tool_result"})
        with self.assertRaisesRegex(ContractError, "source_role_misuse"):
            first.resolve(wire, purpose="audit", allowed_kinds={"user_report"})
        second = SourceCatalog({"t": source}, "window-2")
        with self.assertRaisesRegex(ContractError, "invisible_reference"):
            second.resolve(wire, purpose="audit")


if __name__ == "__main__":
    unittest.main()
