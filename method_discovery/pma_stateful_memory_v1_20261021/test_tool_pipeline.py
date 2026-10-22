"""Offline decoded-Claude fixtures through compilers and original domain gates.

These exercise actual role-tool names, not HTTP, SDK, or SSE integration.
"""
from copy import deepcopy
import unittest

from . import test_tool_decisions as decisions_fixture
from . import test_tool_maintenance as maintenance_fixture
from .audit import validate_audit_result
from .reminder import validate_selection
from .tool_decisions import (audit_tool_definitions, selection_tool_definitions,
                             compile_audit, compile_selection)
from .tool_maintenance import compile_maintenance, tool_definitions
from .tool_native import NativeToolError, normalize_claude_response


def response(calls):
    return {"type": "message", "role": "assistant", "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "id": f"toolu_{index}",
                         "name": call["name"], "input": call["arguments"]}
                        for index, call in enumerate(calls)]}


def normalize(value, definitions):
    # This tuple models the host's frozen request tool list. Completion here is
    # a fixture assertion, not a claim that this helper verifies a transport.
    names = tuple(item["function"]["name"] for item in definitions)
    return normalize_claude_response(value, permitted_tool_names=names,
                                     response_complete=True)["calls"]


class ToolPipelineTests(unittest.TestCase):
    def setUp(self):
        self.decisions = decisions_fixture.ToolDecisionTests()
        self.decisions.setUp()
        self.maintenance = maintenance_fixture.ToolMaintenanceTests()
        self.maintenance.setUp()

    def test_audit_closure_real_name_and_original_gate(self):
        fixture = self.decisions.closure
        args = decisions_fixture.compact(fixture.result())
        native = response([{"name": "submit_audit", "arguments": args}])
        before = deepcopy((native, fixture.view))
        calls = normalize(native, audit_tool_definitions())
        result = compile_audit(calls, view=fixture.view)
        self.assertEqual(result, fixture.result())
        validate_audit_result(result, view=fixture.view, catalog=fixture.catalog)
        self.assertEqual((native, fixture.view), before)

    def test_selection_reminder_real_name_and_original_gate(self):
        fixture = self.decisions
        args = {"decision": "remind", "refs": [fixture.ref],
                "context_for_action": "Check this gap."}
        native = response([{"name": "submit_selection", "arguments": args}])
        before = deepcopy((native, fixture.binding, fixture.snapshot))
        result = compile_selection(normalize(native, selection_tool_definitions()),
                                   binding=fixture.binding)
        validate_selection(result, snapshot=fixture.snapshot,
                           phase2_view_id="v", selected_refs=[fixture.ref])
        self.assertEqual(result["refs"], [fixture.ref])
        self.assertEqual((native, fixture.binding, fixture.snapshot), before)

    def test_nontrivial_maintenance_batch_matches_original_candidate(self):
        fixture = self.maintenance
        entity = {"entity_id": "@artifact", "entity_type": "artifact",
                  "display_name": "check output"}
        state = fixture.arguments(fixture.base["B"]["W"]["states"][0])
        state.update(record_id="@observation", entity_id="@artifact")
        state["scope"]["entity_ids"] = ["@artifact"]
        relation = {"relation_id": "@relation", "from_entity_id": "e",
                    "to_entity_id": "@artifact", "predicate": "produced",
                    "anchored_by": {"type": "state", "record_id": "@observation",
                                    "revision": 1}}
        calls = [{"name": "put_relation", "arguments": relation},
                 {"name": "propose_knowledge", "arguments": state},
                 {"name": "put_entity", "arguments": entity}]
        native = response(calls)
        before = deepcopy((native, fixture.base, fixture.binding))
        result = compile_maintenance(normalize(native, tool_definitions()),
                                     binding=fixture.binding, base=fixture.base)
        expected = fixture.compile(calls)
        self.assertEqual(result, expected)
        candidate = fixture.build(result)
        self.assertEqual(candidate, fixture.build(expected))
        self.assertEqual(len(candidate["candidate"]["B"]["W"]["states"]),
                         len(fixture.base["B"]["W"]["states"]) + 1)
        self.assertEqual((native, fixture.base, fixture.binding), before)

    def test_bad_middle_call_exposes_no_executable_batch_or_host_mutation(self):
        fixture = self.maintenance
        calls = [{"name": "put_entity", "arguments": {
                    "entity_id": "@new", "entity_type": "other", "display_name": "new"}},
                 {"name": "unrequested_tool", "arguments": {}},
                 {"name": "clear_focus", "arguments": {"reason": "done"}}]
        native = response(calls)
        before = deepcopy((native, fixture.base, fixture.binding))
        with self.assertRaises(NativeToolError) as caught:
            normalize(native, tool_definitions())
        self.assertEqual(caught.exception.code, "unpermitted_tool_name")
        self.assertFalse(hasattr(caught.exception, "calls"))
        self.assertEqual((native, fixture.base, fixture.binding), before)

    def test_explicit_refusal_is_not_a_clean_audit(self):
        fixture = self.decisions.closure
        native = response([{"name": "submit_audit", "arguments":
                            decisions_fixture.compact(fixture.result())}])
        native["content"].append({"type": "refusal", "refusal": "Cannot audit."})
        before = deepcopy((native, fixture.view))
        with self.assertRaises(NativeToolError) as caught:
            normalize(native, audit_tool_definitions())
        self.assertEqual(caught.exception.code, "native_refusal")
        self.assertFalse(hasattr(caught.exception, "calls"))
        self.assertEqual((native, fixture.view), before)


if __name__ == "__main__":
    unittest.main()
