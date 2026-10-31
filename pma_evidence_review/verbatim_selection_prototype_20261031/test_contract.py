import json
import unittest
from dataclasses import FrozenInstanceError

from contract import (ContractError, delivery_json, freeze_snapshot, parse_and_render)


VERSION = "task_sha_318ac9"
REVISION = "rev_0985b131ecd044d2b8a443142c37b5a2"
IDS = ("G2ng7ij2", "P7hm2jk4", "K4yu8lo1")
TASK = {"kind": "task", "version": VERSION}


def memory(i, revision=REVISION):
    return {"kind": "memory", "id": i, "revision": revision}


class MockCommittedGate:
    """Explicit fixture, not an implementation of semantic review."""
    def __init__(self):
        self.committed = [
            {"id": i, "revision": REVISION, "category": category,
             "text": f" {category} 原文\t\n\n"}
            for i, category in zip(IDS, ("knowledge", "procedural", "gap"))]
        self.rejected = [{"id": "rejected-id", "revision": "rejected-rev", "category": "knowledge",
                          "text": "Rejected proposal"}]


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.gate = MockCommittedGate()
        self.snapshot = freeze_snapshot("c1", VERSION, "  原任务\r\n不得删减。\t\n",
                                        "内部状态：尚未完成", self.gate.committed)

    def decision(self, refs, decision="intervene", **changes):
        data = {"cycle": "c1", "task_version": VERSION,
                "decision": decision, "references": refs}
        data.update(changes)
        return json.dumps(data, ensure_ascii=False)

    def run_output(self, raw, **active):
        kwargs = {"active_cycle": "c1", "active_task_version": VERSION}
        kwargs.update(active)
        return parse_and_render(raw, self.snapshot, **kwargs)

    def assert_error(self, raw, code=None, **active):
        result = self.run_output(raw, **active)
        self.assertEqual(result.kind, "error")
        self.assertEqual(result.blocks, ())
        if code:
            self.assertEqual(result.error, code)

    def test_task_only_exact_unicode_and_whitespace(self):
        result = self.run_output(self.decision([TASK]))
        self.assertEqual(result.kind, "intervention")
        self.assertEqual(result.blocks[0].text, self.snapshot.task_text)
        encoded = delivery_json(result)
        self.assertEqual(json.loads(encoded)["blocks"][0]["text"],
                         "  原任务\r\n不得删减。\t\n")
        self.assertEqual(encoded, delivery_json(result))
        self.assertNotIn("内部状态", encoded)

    def test_each_category_and_mixed_requested_order(self):
        for index, i in enumerate(IDS):
            with self.subTest(id=i):
                result = self.run_output(self.decision([memory(i)]))
                self.assertEqual(result.kind, "intervention")
                self.assertEqual(result.blocks[0].text,
                                 self.gate.committed[index]["text"])
        result = self.run_output(self.decision([memory(IDS[2]), TASK, memory(IDS[0])]))
        self.assertEqual([b.text for b in result.blocks],
                         [self.gate.committed[2]["text"], self.snapshot.task_text,
                          self.gate.committed[0]["text"]])

    def test_no_intervention_and_hidden_gap_not_deleted(self):
        before = [dict(r) for r in self.gate.committed]
        result = self.run_output(self.decision([], "no_intervention"))
        self.assertEqual((result.kind, result.blocks, result.error),
                         ("no_intervention", (), None))
        self.run_output(self.decision([memory(IDS[0])]))
        self.assertEqual(self.gate.committed, before)
        self.assertEqual(self.snapshot.items[2].category, "gap")

    def test_internal_status_unknown_id_revision_and_rejected_item(self):
        cases = [({"kind": "status"}, "unselectable_reference_kind"),
                 (memory("missing-id"), "unknown_memory_id"),
                 (memory(IDS[0], "wrong-rev"), "wrong_memory_revision"),
                 (memory("rejected-id", "rejected-rev"), "unknown_memory_id")]
        for ref, error in cases:
            with self.subTest(ref=ref):
                # Valid preceding reference must not leak as partial delivery.
                self.assert_error(self.decision([TASK, ref]), error)

    def test_selector_cannot_inject_text_or_approval(self):
        for field in ("text", "note", "approved"):
            with self.subTest(field=field):
                self.assert_error(self.decision([TASK], **{field: "injected"}),
                                  "invalid_decision_fields")
                self.assert_error(self.decision([{**memory(IDS[0]), field: True}]),
                                  "invalid_memory_reference")

    def test_decision_conflicts_and_duplicates_are_errors(self):
        self.assert_error(self.decision([]), "decision_selection_conflict")
        self.assert_error(self.decision([TASK], "no_intervention"),
                          "decision_selection_conflict")
        for ref in (TASK, memory(IDS[0])):
            self.assert_error(self.decision([ref, ref]), "duplicate_reference")

    def test_invalid_json_and_types(self):
        for raw in (None, b"{}", "{", "```json\n{}\n```", "[]", "null",
                    '{"cycle":"c1","cycle":"c1"}', '{"x":NaN}',
                    self.decision("task"), self.decision([None]),
                    self.decision([{"kind": []}]),
                    self.decision([memory(True)]),
                    self.decision([memory(IDS[0], 2.0)]),
                    self.decision([TASK], task_version=True),
                    self.decision([TASK], decision=False)):
            with self.subTest(raw=raw):
                self.assert_error(raw)

    def test_frozen_snapshot_survives_live_edit_delete_and_replacement(self):
        original = self.snapshot.items[0].text
        self.gate.committed[0]["text"] = "Changed live text"
        self.gate.committed[0]["revision"] = "changed-rev"
        self.gate.committed.clear()
        self.gate.committed.append({"id": IDS[0], "revision": "replacement-rev",
                                    "category": "knowledge", "text": "Reused ID"})
        result = self.run_output(self.decision([memory(IDS[0])]))
        self.assertEqual(result.blocks[0].text, original)
        with self.assertRaises(FrozenInstanceError):
            self.snapshot.items[0].text = "overwrite"
        with self.assertRaises(FrozenInstanceError):
            self.snapshot.internal_status = "overwrite"

    def test_stale_identity_in_output_or_host_context_is_error(self):
        for changes in ({"cycle": "old"}, {"task_version": "old-task"}):
            self.assert_error(self.decision([TASK], **changes))
        for active in ({"active_cycle": "c2"}, {"active_task_version": "new-task"}):
            self.assert_error(self.decision([TASK]), "stale_snapshot", **active)
            self.assert_error(self.decision([], "no_intervention"),
                              "stale_snapshot", **active)
        self.assert_error(self.decision([{"kind": "task", "version": "old-task"}]),
                          "wrong_task_reference_version")

    def test_large_selector_and_host_text_are_not_capped_or_truncated(self):
        long_text = "字\t\n" * 30000
        records = [{"id": f"native-{i}", "revision": REVISION,
                    "category": "knowledge", "text": f"entry-{i}"}
                   for i in range(140)]
        snapshot = freeze_snapshot("c1", VERSION, long_text, "private", records)
        refs = [memory(record["id"]) for record in records] + [TASK]
        raw = " " * 70000 + self.decision(refs)
        result = parse_and_render(raw, snapshot, active_cycle="c1",
                                  active_task_version=VERSION)
        self.assertEqual(result.kind, "intervention")
        self.assertEqual(len(result.blocks), 141)
        self.assertEqual([b.text for b in result.blocks[:-1]],
                         [record["text"] for record in records])
        self.assertEqual(result.blocks[-1].text, long_text)

    def test_native_opaque_identities_are_preserved(self):
        result = self.run_output(self.decision([TASK, memory(IDS[0])]))
        payload = json.loads(delivery_json(result))
        self.assertEqual(payload["blocks"][0]["reference"], TASK)
        self.assertEqual(payload["blocks"][1]["reference"], memory(IDS[0]))
        self.assertEqual(self.snapshot.task_version, VERSION)
        self.assertEqual(self.snapshot.items[0].id, IDS[0])
        self.assertEqual(self.snapshot.items[0].revision, REVISION)
        # Opaque means no trimming, coercion or interpretation, even for spaces.
        snapshot = freeze_snapshot("c1", " hash ", "task", "status",
                                   [{"id": " id ", "revision": " rev ",
                                     "category": "gap", "text": "body"}])
        raw = self.decision([{"kind": "task", "version": " hash "},
                             memory(" id ", " rev ")], task_version=" hash ")
        result = parse_and_render(raw, snapshot, active_cycle="c1",
                                  active_task_version=" hash ")
        self.assertEqual(result.kind, "intervention")
        self.assertEqual(result.blocks[1].reference.id, " id ")

    def test_surrogate_text_and_opaque_identities_have_utf8_safe_delivery(self):
        version, item_id, revision = "task-\ud800", "id-\ud801", "rev-\udfff"
        task_text, memory_text = "task\ud800\t\n", "memory\udfff\r\n"
        snapshot = freeze_snapshot("cycle-\ud802", version, task_text, "private",
                                   [{"id": item_id, "revision": revision,
                                     "category": "knowledge", "text": memory_text}])
        refs = [{"kind": "task", "version": version}, memory(item_id, revision)]
        raw = json.dumps({"cycle": snapshot.cycle, "task_version": version,
                          "decision": "intervene", "references": refs})
        result = parse_and_render(raw, snapshot, active_cycle=snapshot.cycle,
                                  active_task_version=version)
        self.assertEqual(result.kind, "intervention")
        wire = delivery_json(result).encode("utf-8")
        self.assertTrue(wire.isascii())
        decoded = json.loads(wire)
        self.assertEqual([block["text"] for block in decoded["blocks"]],
                         [task_text, memory_text])
        self.assertEqual([block["reference"] for block in decoded["blocks"]], refs)

    def test_identity_fields_require_nonempty_strings(self):
        for bad in ("", None, True, 1, 1.0, [], {}):
            with self.subTest(value=bad):
                self.assert_error(self.decision([memory(bad)]))
                self.assert_error(self.decision([memory(IDS[0], bad)]))
                self.assert_error(self.decision([TASK], task_version=bad))
                self.assert_error(self.decision([{"kind": "task", "version": bad}]))
                with self.assertRaises(ContractError):
                    freeze_snapshot("c1", bad, "task", "status", [])
                for field in ("id", "revision"):
                    with self.assertRaises(ContractError):
                        freeze_snapshot("c1", VERSION, "task", "status",
                                        [{**self.gate.committed[0], field: bad}])

    def test_host_adapter_rejects_ambiguous_committed_records(self):
        record = self.gate.committed[0]
        for records in ([record, record], [{**record, "approved": True}],
                        [{**record, "category": "status"}],
                        [{**record, "revision": True}]):
            with self.subTest(records=records), self.assertRaises(ContractError):
                freeze_snapshot("c1", VERSION, "task", "status", records)


if __name__ == "__main__":
    unittest.main()
