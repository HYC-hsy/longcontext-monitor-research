"""V3 message-boundary counterexamples; fake provider and local store only."""

from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path

from .engine import CycleEngine
from .proposal import build_candidate
from .source import SourceCatalog
from .source import ContractError, canonical
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf
from .test_engine import ScriptedProvider, event
from .test_schema_advanced import rich_state


def seeded_store(path, *, historical_state=False, repeated_user=False,
                 retired_requirement=False):
    seed, ledger = rich_state()
    if repeated_user:
        ledger["u0"] = leaf("task task")
        seed["B"]["G"]["specifications"][0]["source_refs"] = [{
            "source_id": "u0", "start": 5, "end": 9, "quote": "task"}]
    requirement = seed["B"]["G"]["specifications"][0]
    if retired_requirement:
        replacement = {**deepcopy(requirement), "requirement_id": "replacement"}
        requirement["status"] = "superseded"
        requirement["retirement"] = {"kind": "interpretation_replaced",
            "replacement_requirement_refs": [{"type": "requirement",
                "requirement_id": "replacement", "revision": 1,
                "task_version": 1}], "source_refs": deepcopy(requirement["source_refs"])}
        seed["B"]["G"]["specifications"].append(replacement)
        for gap in seed["B"]["DeltaE"] + seed["B"]["DeltaA"]:
            gap["goal_refs"][0]["requirement_id"] = "replacement"
    archive_delta = []
    if historical_state:
        old = deepcopy(seed["B"]["W"]["states"][0])
        head = seed["B"]["W"]["states"][0]
        head["revision"] = 2
        head["claim"]["text"] = "current revised observation"
        head["supersedes"] = [{"type": "state", "record_id": "s", "revision": 1}]
        seed["B"]["W"]["relations"][0]["anchored_by"]["revision"] = 2
        archive_delta = [("state", "s", 1, old)]
    store = MemoryStore(path)
    store.initialize(empty_snapshot(), ledger["u0"])
    action = leaf("read_file", source_id="action", source_kind="executed_action")
    action.update(event_id="tool-use", event_seq=1, ga_turn=1,
                  field_path="actions.0.arguments")
    store.append_event({"event_id": "batch-1", "event_seq": 1,
        "kind": "action_batch", "occurred_at_step": 1,
        "source_ids": ["action", "tool"],
        "payload": {"actions": [{"tool_use_id": "tool-use"}]}},
        [action, ledger["tool"]])
    store.compare_and_swap(update_id="seed", cycle_id="seed",
        base=store.snapshot(), candidate=seed, archive_delta=archive_delta)
    store.append_event(*event(2, "next result"))
    return store


class ClosureV3Tests(unittest.TestCase):
    def test_transition_version_record_rolls_back_with_commit(self):
        with tempfile.TemporaryDirectory() as root:
            store = seeded_store(Path(root) / "db")
            try:
                before = store.snapshot()
                store.db.execute("CREATE TRIGGER reject_version BEFORE INSERT ON "
                    "commit_versions BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
                inner = ScriptedProvider()
                def provider(role, messages, call_id, max_output):
                    answer = inner(role, messages, call_id, max_output)
                    if role != "maintenance":
                        return answer
                    payload = json.loads(messages[1]["content"])
                    evidence = next(item for item in payload["source_catalog"] if
                        item["source_id"] == "tool-2" and item["purpose"] ==
                        "maintenance")
                    parsed = json.loads(answer)
                    parsed["world_patch"]["record_transitions"] = [{
                        "record_ref": {"type": "state", "record_id": "s",
                                       "revision": 1}, "to_status": "contested",
                        "reason": "synthetic contradiction", "evidence_refs": [{
                            "evidence_id": evidence["evidence_id"],
                            "quote": "next result"}]}]
                    return canonical(parsed).decode()
                result = CycleEngine(store, provider, task_text="task").run(
                    "abort-version")
                self.assertEqual(result["status"], "runtime_failed")
                self.assertEqual(store.snapshot(), before)
                self.assertEqual(store.archive(), {})
                self.assertEqual(store.db.execute("SELECT count(*) FROM "
                    "commit_versions").fetchone()[0], 1)
                self.assertIsNone(store.commit_for_cycle(result["cycle_id"]))
            finally:
                store.close()

    def test_transition_reason_survives_restart_and_commit_identity(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "db"
            store = seeded_store(path)
            captured = {}
            actual_cas = store.compare_and_swap
            def spy(**kwargs):
                captured.update(deepcopy(kwargs))
                return actual_cas(**kwargs)
            store.compare_and_swap = spy
            inner = ScriptedProvider()
            def provider(role, messages, call_id, max_output):
                answer = inner(role, messages, call_id, max_output)
                if role == "maintenance":
                    payload = json.loads(messages[1]["content"])
                    span = next(item for item in payload["source_catalog"] if
                        item["source_id"] == "tool-2" and item["purpose"] ==
                        "maintenance")
                    parsed = json.loads(answer)
                    parsed["world_patch"]["record_transitions"] = [{
                        "record_ref": {"type": "state", "record_id": "s",
                                       "revision": 1},
                        "to_status": "historical_only", "reason": "new observation",
                        "evidence_refs": [{"evidence_id": span["evidence_id"],
                                           "quote": "next result"}]}]
                    return canonical(parsed).decode()
                return answer
            try:
                result = CycleEngine(store, provider, task_text="task").run(
                    "transition")
                self.assertEqual(result["status"], "committed_selection_silent")
                audit = json.loads(next(item for item in inner.calls if item[
                    "role"] == "audit")["messages"][1]["content"])
                operation = next(item for item in audit["operation_index"] if
                                 item["operation"] == "record_transitions")
                self.assertEqual(operation["reason"], "new observation")
                self.assertEqual(operation["before_ref"]["revision"], 1)
                self.assertEqual(operation["after_ref"]["revision"], 2)
                self.assertEqual(len(operation["evidence_refs"]), 1)
                evidence_id = operation["evidence_refs"][0]["evidence_id"]
                self.assertTrue(any(item["evidence_id"] == evidence_id for item
                                    in audit["source_catalog"]))
                update_id = result["commit"]["update_id"]
            finally:
                store.close()
            reopened = MemoryStore(path)
            try:
                change = reopened.version_changes(update_id)[0]
                self.assertEqual(change["reason"], "new observation")
                self.assertEqual(change["evidence_refs"][0]["source_id"], "tool-2")
                self.assertEqual(reopened.state_version_change("s", 2), change)
                self.assertEqual(reopened.compare_and_swap(**captured), result[
                    "commit"])
                altered = deepcopy(captured)
                altered["transition_changes"][0]["reason"] = "different reason"
                with self.assertRaisesRegex(ContractError, "identity_conflict"):
                    reopened.compare_and_swap(**altered)
            finally:
                reopened.close()

    def test_committed_retirement_keeps_exact_old_replacement(self):
        with tempfile.TemporaryDirectory() as root:
            store = seeded_store(Path(root) / "db", repeated_user=True,
                                 retired_requirement=True)
            try:
                before = store.snapshot()
                active = next(item for item in before["B"]["G"]["specifications"]
                              if item["requirement_id"] == "replacement")
                catalog = SourceCatalog(store.sources(), "retirement-window")
                user = catalog.add("u0", 5, 9, "maintenance",
                                   exact_stored_ref=True)
                patch = {"protocol": "maintenance-proposal/1", "request_id": "revise",
                    "active_task_version": 1, "base_state_version": 1,
                    "world_patch": {"entity_upserts": [], "state_upserts": [],
                        "relation_upserts": [], "record_transitions": []},
                    "specification_upserts": [{**active, "revision": 2,
                        "interpretation": "revised interpretation", "source_refs": [{
                            "evidence_id": user.evidence_id, "quote": "task"}]}],
                    "gap_upserts": [], "gap_resolutions": [], "gap_reopens": [],
                    "focus": {"op": "keep"}}
                for gap in before["B"]["DeltaE"] + before["B"]["DeltaA"]:
                    updated = deepcopy(gap)
                    updated["revision"] = 2
                    updated["goal_refs"][0]["revision"] = 2
                    patch["gap_upserts"].append(updated)
                built = build_candidate(proposal=patch, base=before,
                    catalog=catalog, cycle_id="revise", processed_to=2,
                    goal_ledger=store.goals(), archive=store.archive(),
                    visible_existing_ids={("requirement", "replacement"),
                        ("gap", "ge"), ("gap", "ga"), ("state", "s")})
                store.compare_and_swap(update_id=built["update_id"],
                    cycle_id="revise", base=before, candidate=built["candidate"],
                    archive_delta=built["archive_delta"])
                current = store.snapshot()
                old = next(item for item in current["B"]["G"]["specifications"]
                           if item["requirement_id"] == "req")
                self.assertEqual(old["retirement"]["replacement_requirement_refs"][0][
                    "revision"], 1)
                self.assertIn(("requirement", "replacement", 1), store.archive())
                new = deepcopy(current)
                new["state_version"] += 1
                new["B"]["G"]["specifications"].append({**deepcopy(old),
                    "requirement_id": "copied-retirement", "revision": 1})
                with self.assertRaisesRegex(ContractError,
                                            "invalid_requirement_replacement"):
                    store.compare_and_swap(update_id="copied", cycle_id="copied",
                        base=current, candidate=new, archive_delta=[])
                self.assertEqual(store.snapshot(), current)
                with self.assertRaisesRegex(ContractError, "version_mismatch"):
                    invalid = deepcopy(current)
                    invalid["B"]["G"]["specifications"][0]["retirement"][
                        "replacement_requirement_refs"][0]["revision"] = 99
                    from .schema import validate_snapshot
                    validate_snapshot(invalid, store.sources(), store.archive(),
                                      store.goals()["deltas"])
            finally:
                store.close()

    def test_current_requirement_exact_alias_reused_through_revision(self):
        with tempfile.TemporaryDirectory() as root:
            store = seeded_store(Path(root) / "db", repeated_user=True)
            try:
                inner = ScriptedProvider()
                def provider(role, messages, call_id, max_output):
                    answer = inner(role, messages, call_id, max_output)
                    if role != "maintenance":
                        return answer
                    payload = json.loads(messages[1]["content"])
                    aliases = [item for item in payload["source_catalog"] if
                        item["source_id"] == "u0" and item["purpose"] ==
                        "maintenance" and item["exact_stored_ref"] and
                        (item["start"], item["end"]) == (5, 9)]
                    self.assertEqual(len(aliases), 1)
                    patch = json.loads(answer)
                    before = payload["before_view"]["B"]
                    prior = before["G"]["specifications"][0]
                    patch["specification_upserts"] = [{**prior, "revision": 2,
                        "source_refs": [{"evidence_id": aliases[0]["evidence_id"],
                                         "quote": "task"}]}]
                    for gap in before["DeltaE"] + before["DeltaA"]:
                        updated = deepcopy(gap)
                        updated["revision"] = 2
                        updated["goal_refs"][0]["revision"] = 2
                        patch["gap_upserts"].append(updated)
                    return canonical(patch).decode()
                result = CycleEngine(store, provider, task_text="task").run("exact-r")
                self.assertEqual(result["status"], "committed_selection_silent")
                for role in ("maintenance", "audit", "selection"):
                    payload = json.loads(next(call for call in inner.calls if call[
                        "role"] == role)["messages"][1]["content"])
                    self.assertTrue(any(item["source_id"] == "u0" and item[
                        "exact_stored_ref"] and (item["start"], item["end"]) ==
                        (5, 9) for item in payload["source_catalog"]))
            finally:
                store.close()

    def test_retirement_alias_and_old_state_selection_context(self):
        with tempfile.TemporaryDirectory() as root:
            store = seeded_store(Path(root) / "db", historical_state=True,
                                 repeated_user=True, retired_requirement=True)
            try:
                provider = ScriptedProvider()
                result = CycleEngine(store, provider, task_text="task").run("history")
                self.assertEqual(result["status"], "committed_selection_silent")
                for role in ("maintenance", "audit", "selection"):
                    payload = json.loads(next(call for call in provider.calls if
                        call["role"] == role)["messages"][1]["content"])
                    self.assertTrue(any(item["source_id"] == "u0" and item[
                        "exact_stored_ref"] and (item["start"], item["end"]) ==
                        (5, 9) for item in payload["source_catalog"]))
                select = json.loads(provider.calls[-1]["messages"][1]["content"])
                old = next(item for item in select["contextual_objects"] if item[
                    "kind"] == "archived_state" and item["record_ref"][
                    "revision"] == 1)
                self.assertEqual(old["body"]["claim"]["text"], "feature absent")
                heads = select["committed_view"]["B"]["W"]["states"]
                self.assertEqual(heads[0]["revision"], 2)
                self.assertNotIn(old["record_ref"], select["selected_refs"])
                self.assertIn({"type": "state", "record_id": "s", "revision": 2},
                              select["selected_refs"])
            finally:
                store.close()
