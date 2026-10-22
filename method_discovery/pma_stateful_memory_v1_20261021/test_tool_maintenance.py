"""Offline compiler equivalence and fail-closed tests; no provider calls."""
from copy import deepcopy
import unittest

from .proposal import build_candidate
from .source import ContractError, SourceCatalog, digest
from .test_contracts import empty_snapshot, leaf
from .test_proposal import proposal
from .test_schema_advanced import rich_state
from .tool_maintenance import compile_maintenance, tool_definitions


def call(name, arguments):
    return {"name": name, "arguments": arguments}


class ToolMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.base, self.ledger = rich_state()
        self.catalog = SourceCatalog(self.ledger, "window")
        self.evidence = {}
        for key, source in self.ledger.items():
            span = self.catalog.add(key, 0, len(source["text"]), "maintenance")
            self.evidence[key] = {"evidence_id": span.evidence_id, "quote": source["text"]}
        self.binding = {"request_id": "request", "active_task_version": 1,
            "base_state_version": 1, "base_state_hash": digest(self.base),
            "task_id": "task", "episode_id": "episode"}
        self.visible = {("entity", "e"), ("state", "s"), ("relation", "link"),
                        ("requirement", "req"), ("gap", "ge"), ("gap", "ga")}
        self.archive = {}

    def compile(self, calls):
        return compile_maintenance(calls, binding=self.binding, base=self.base)

    def build(self, patch):
        return build_candidate(proposal=patch, base=self.base, catalog=self.catalog,
            cycle_id="cycle", processed_to=1, goal_ledger={"epoch": 1,
            "deltas": {}, "messages": ["u0"]}, visible_existing_ids=self.visible,
            archive=self.archive)

    def wire(self, value):
        if type(value) is list:
            return [self.wire(item) for item in value]
        if type(value) is dict:
            if set(value) == {"source_id", "start", "end", "quote"}:
                return deepcopy(self.evidence[value["source_id"]])
            return {key: self.wire(item) for key, item in value.items()}
        return value

    def arguments(self, item):
        result = self.wire(item)
        result.pop("revision", None)
        result.pop("kind", None)
        return result

    def test_all_six_groups_equivalent_to_wire_proposal_and_candidate(self):
        expected = proposal()
        expected["base_state_version"] = 1
        entity = {"entity_id": "@new_entity", "entity_type": "artifact", "display_name": "output"}
        state = self.wire(self.base["B"]["W"]["states"][0])
        state.update(record_id="@state", revision=1, entity_id="@new_entity")
        state["scope"]["entity_ids"] = ["@new_entity"]
        requirement = self.wire(self.base["B"]["G"]["specifications"][0])
        requirement.update(requirement_id="@requirement", revision=1)
        gap = deepcopy(self.base["B"]["DeltaA"][0])
        gap.update(gap_id="@gap", revision=1)
        gap["goal_refs"][0]["requirement_id"] = "@requirement"
        relation = {"relation_id": "@relation", "from_entity_id": "e",
            "to_entity_id": "@new_entity", "predicate": "produced",
            "anchored_by": {"type": "state", "record_id": "@state", "revision": 1}}
        focus = {"gap_ref": {"type": "gap", "gap_id": "@gap", "revision": 1,
                            "task_version": 1}, "reason": "investigate", "changed_at_step": 3}
        expected["world_patch"]["entity_upserts"] = [entity]
        expected["world_patch"]["state_upserts"] = [state]
        expected["world_patch"]["relation_upserts"] = [relation]
        expected["specification_upserts"] = [requirement]
        expected["gap_upserts"] = [gap]
        expected["focus"] = {"op": "set", "value": focus}
        calls = [call("set_focus", focus), call("put_relation", relation),
            call("propose_knowledge", self.arguments(state)), call("put_entity", entity),
            call("open_gap", self.arguments(gap)), call("put_requirement", self.arguments(requirement))]
        untouched = deepcopy((self.base, self.binding, calls))
        actual = self.compile(calls)
        self.assertEqual(actual, expected)
        self.assertEqual(self.build(actual), self.build(expected))
        self.assertEqual((self.base, self.binding, calls), untouched)

    def test_no_change_explicit_and_exclusive(self):
        actual = self.compile([call("memory_no_change", {})])
        expected = proposal()
        expected["base_state_version"] = 1
        self.assertEqual(actual, expected)
        self.build(actual)
        for calls in ([], [call("memory_no_change", {}), call("clear_focus", {"reason": "done"})]):
            with self.assertRaises(ContractError):
                self.compile(calls)

    def test_revision_and_past_reference_preserved(self):
        old = deepcopy(self.base["B"]["W"]["states"][0])
        self.archive[("s", 1)] = old
        current = self.base["B"]["W"]["states"][0]
        current.update(revision=2, supersedes=[{"type": "state", "record_id": "s", "revision": 1}])
        self.binding["base_state_hash"] = digest(self.base)
        args = self.arguments(current)
        args["supersedes"].append({"type": "state", "record_id": "s", "revision": 2})
        args["claim"]["time_role"] = "past_episode"
        args["updated_at_step"] = 17
        relation = deepcopy(self.base["B"]["W"]["relations"][0])
        result = self.compile([call("propose_knowledge", args), call("put_relation", relation)])
        new = result["world_patch"]["state_upserts"][0]
        self.assertEqual(new["revision"], 3)
        self.assertEqual(new["updated_at_step"], 17)
        self.assertEqual(new["claim"]["time_role"], "past_episode")
        self.assertEqual(new["supersedes"][0]["revision"], 1)
        self.assertEqual(result["world_patch"]["relation_upserts"][0]["anchored_by"]["revision"], 1)
        self.build(result)

    def test_archived_only_supersedes_equivalent_to_valid_original_candidate(self):
        archived = deepcopy(self.base["B"]["W"]["states"][0])
        archived["record_id"] = "archived-only"
        self.archive[("archived-only", 1)] = archived
        state = self.wire(self.base["B"]["W"]["states"][0])
        state.update(record_id="@new", revision=1, supersedes=[
            {"type": "state", "record_id": "archived-only", "revision": 1}])
        expected = proposal()
        expected["base_state_version"] = 1
        expected["world_patch"]["state_upserts"] = [state]
        # Establish old-contract validity before exercising the new compiler.
        original = self.build(expected)
        actual = self.compile([call("propose_knowledge", self.arguments(state))])
        self.assertEqual(actual, expected)
        self.assertEqual(self.build(actual), original)
        missing_archive = self.archive
        self.archive = {}
        with self.assertRaisesRegex(ContractError, "version_mismatch"):
            self.build(actual)
        self.archive = missing_archive

    def test_unchanged_retirement_preserves_archived_only_requirement(self):
        requirement = self.base["B"]["G"]["specifications"][0]
        archived = deepcopy(requirement)
        archived["requirement_id"] = "archived-replacement"
        self.archive[("requirement", "archived-replacement", 1)] = archived
        requirement.update(status="superseded", retirement={
            "kind": "interpretation_replaced", "source_refs": deepcopy(requirement["source_refs"]),
            "replacement_requirement_refs": [{"type": "requirement",
                "requirement_id": "archived-replacement", "revision": 1, "task_version": 1}]})
        self.base["B"]["DeltaE"] = []
        self.base["B"]["DeltaA"] = []
        self.binding["base_state_hash"] = digest(self.base)
        updated = self.wire(requirement)
        updated["revision"] = 2
        expected = proposal()
        expected["base_state_version"] = 1
        expected["specification_upserts"] = [updated]
        original = self.build(expected)
        actual = self.compile([call("put_requirement", self.arguments(updated))])
        self.assertEqual(actual, expected)
        self.assertEqual(self.build(actual), original)

    def test_historical_ref_deferral_does_not_allow_unknown_or_wrong_type_locals(self):
        state = self.arguments(self.base["B"]["W"]["states"][0])
        state["record_id"] = "@state"
        for identifier in ("@unknown", "@entity"):
            state["supersedes"] = [{"type": "state", "record_id": identifier, "revision": 1}]
            with self.subTest(identifier=identifier), self.assertRaises(ContractError):
                self.compile([call("put_entity", {"entity_id": "@entity", "entity_type": "other",
                    "display_name": "new"}), call("propose_knowledge", state)])

    def test_transition_and_clear_focus(self):
        transition = {"record_ref": {"type": "state", "record_id": "s", "revision": 1},
            "to_status": "historical_only", "reason": "past observation",
            "evidence_refs": [self.evidence["tool"]]}
        result = self.compile([call("transition_record", transition),
                               call("clear_focus", {"reason": "no focus"})])
        self.assertEqual(result["world_patch"]["record_transitions"], [transition])
        self.assertEqual(self.build(result)["candidate"]["B"]["W"]["states"][0]["revision"], 2)

    def test_gap_revise_resolve_reopen(self):
        args = self.arguments(self.base["B"]["DeltaE"][0])
        revised = self.compile([call("revise_gap", args)])
        self.assertEqual(revised["gap_upserts"][0]["revision"], 2)
        self.build(revised)
        args.update(status="supported", closure={"kind": "environment_supported",
            "conclusion": "absence observed", "evidence_refs": [self.evidence["tool"]],
            "state_refs": [{"type": "state", "record_id": "s", "revision": 1}]})
        resolved = self.compile([call("resolve_gap", args)])
        self.base = self.build(resolved)["candidate"]
        self.binding.update(base_state_version=2, base_state_hash=digest(self.base))
        args.update(status="open", closure=None)
        reopened = self.compile([call("reopen_gap", args)])
        self.assertEqual(reopened["gap_reopens"][0]["revision"], 3)
        self.build(reopened)

    def test_experience_preserves_episode_lesson_source_and_time_roles(self):
        action = leaf("ran check", source_id="action", source_kind="executed_action")
        self.ledger["action"] = action
        self.catalog = SourceCatalog(self.ledger, "window")
        for key, source in self.ledger.items():
            span = self.catalog.add(key, 0, len(source["text"]), "maintenance")
            self.evidence[key] = {"evidence_id": span.evidence_id, "quote": source["text"]}
        args = self.arguments(self.base["B"]["W"]["states"][0])
        condition = args.pop("claim")
        condition["time_role"] = "past_episode"
        args.update(record_id="@experience", episode={"conditions": condition,
            "action_text": "ran check", "action_refs": [self.evidence["action"]],
            "result": deepcopy(condition), "time_role": "past_episode"},
            lesson={"text": "check first", "assertion_origin": "inference",
                "time_role": "general_hypothesis", "support_refs": [self.evidence["tool"]],
                "challenge_refs": []})
        compiled = self.compile([call("propose_experience", args)])
        state = compiled["world_patch"]["state_upserts"][0]
        self.assertEqual(state["kind"], "procedural")
        self.assertEqual(state["episode"], args["episode"])
        self.build(compiled)

    def test_malformed_or_conflicting_batches_are_atomic(self):
        entity = {"entity_id": "@e", "entity_type": "other", "display_name": "new"}
        state = self.arguments(self.base["B"]["W"]["states"][0])
        state["record_id"] = "@s"
        invalid = [
            [call("unknown", {})], [call("put_entity", {**entity, "fact": True})],
            [call("put_entity", entity), call("put_entity", entity)],
            [call("set_focus", {"gap_ref": {"type": "gap", "gap_id": "s", "revision": 1,
                "task_version": 1}, "reason": "wrong kind", "changed_at_step": 1})],
            [call("propose_knowledge", {**state, "updated_at_step": True})],
            [call("propose_knowledge", {**state, "entity_id": "unseen"})],
            [call("clear_focus", {"reason": "one"}), call("clear_focus", {"reason": "two"})],
            [call("transition_record", {"record_ref": {"type": "state", "record_id": "s", "revision": 2},
                "to_status": "retracted", "reason": "stale", "evidence_refs": []})],
            [call("revise_gap", {**self.arguments(self.base["B"]["DeltaE"][0]), "gap_id": "@new"})],
            [call("put_entity", entity), {"name": "clear_focus", "arguments": {"reason": "x"}, "extra": 1}],
        ]
        before = deepcopy(self.base)
        for batch in invalid:
            with self.subTest(batch=batch), self.assertRaises(ContractError):
                self.compile(batch)
            self.assertEqual(self.base, before)

    def test_semantic_epoch_retirement_and_historical_refs_not_rewritten(self):
        self.binding["active_task_version"] = 2
        args = self.arguments(self.base["B"]["G"]["specifications"][0])
        delta = {"type": "goal_delta", "goal_delta_id": "changed",
                 "from_task_version": 1, "to_task_version": 2}
        args.update(status="superseded", retirement={"kind": "goal_changed", "goal_delta_ref": delta})
        result = self.compile([call("put_requirement", args)])
        requirement = result["specification_upserts"][0]
        self.assertEqual(requirement["revision"], 2)
        self.assertEqual(requirement["task_version"], 1)
        self.assertEqual(requirement["retirement"]["goal_delta_ref"], delta)
        self.assertEqual(result["active_task_version"], 2)

    def test_static_cross_field_errors_rejected_before_candidate(self):
        args = self.arguments(self.base["B"]["W"]["states"][0])
        args.update(record_id="@new")
        bad_claim = deepcopy(args)
        bad_claim["claim"]["assertion_origin"] = "inference"
        bad_scope = deepcopy(args)
        bad_scope["scope"]["task_id"] = "other task"
        gap = self.arguments(self.base["B"]["DeltaE"][0])
        gap.update(status="supported", closure=None)
        requirement = self.arguments(self.base["B"]["G"]["specifications"][0])
        requirement["status"] = "superseded"
        for name, item in (("propose_knowledge", bad_claim),
                ("propose_knowledge", bad_scope), ("resolve_gap", gap),
                ("put_requirement", requirement)):
            with self.subTest(name=name), self.assertRaises(ContractError):
                self.compile([call(name, item)])

    def test_python_only_arguments_reject_as_contract_errors_atomically(self):
        cyclic = {}
        cyclic["self"] = cyclic
        huge_integer = 10 ** 5000
        state = self.arguments(self.base["B"]["W"]["states"][0])
        state.update(record_id="@new", updated_at_step=huge_integer)
        batches = [
            [call("memory_no_change", {1: 0, "extra": 0})],
            [call("memory_no_change", cyclic)],
            [call("propose_knowledge", state)],
            [{1: 0, "extra": 0}],
            [call("memory_no_change", {}), {"name": "unknown", "arguments": {}}],
            [call("memory_no_change", "{}")],
        ]
        before = deepcopy(self.base)
        for index, batch in enumerate(batches):
            with self.subTest(index=index), self.assertRaises(ContractError):
                self.compile(batch)
            self.assertEqual(self.base, before)

    def test_stale_binding_fails(self):
        for key, value in (("base_state_version", 0), ("base_state_hash", "wrong"), ("task_id", "wrong")):
            binding = {**self.binding, key: value}
            with self.assertRaises(ContractError):
                compile_maintenance([call("memory_no_change", {})], binding=binding, base=self.base)

    def test_definitions_are_closed_and_defensively_copied(self):
        definitions = tool_definitions()
        self.assertEqual(len(definitions), 13)
        def check(schema):
            if schema.get("type") == "object":
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(set(schema["required"]), set(schema["properties"]))
                for child in schema["properties"].values():
                    check(child)
            for child in schema.get("anyOf", []):
                check(child)
            if "items" in schema:
                check(schema["items"])
        for definition in definitions:
            check(definition["function"]["parameters"])
        definitions[0]["function"]["parameters"]["properties"].clear()
        self.assertTrue(tool_definitions()[0]["function"]["parameters"]["properties"])

    def test_host_gate_still_rejects_visibility_and_false_quotes(self):
        relation = deepcopy(self.base["B"]["W"]["relations"][0])
        compiled = self.compile([call("put_relation", relation)])
        self.visible.remove(("state", "s"))
        with self.assertRaisesRegex(ContractError, "invisible_existing_reference"):
            self.build(compiled)
        args = self.arguments(self.base["B"]["G"]["specifications"][0])
        args["source_refs"][0]["quote"] = "invented"
        compiled = self.compile([call("put_requirement", args)])
        with self.assertRaises(ContractError):
            self.build(compiled)


if __name__ == "__main__":
    unittest.main()
