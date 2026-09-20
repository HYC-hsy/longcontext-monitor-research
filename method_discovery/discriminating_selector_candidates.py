"""Single-call G/E selectors for decision-discriminating evidence acquisition.

Both modes see the same complete parent History and use the same selector tool.
The host validates the protocol and executes exactly one nested existing read/search
action.  It deliberately does not judge whether the premise or outcomes are sound.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from monitor_agent_core.actions import ToolOutcome
from monitor_agent_core.workspace import MonitorWorkspace

from decision_question_diagnostic import (
    CallBudget, _clone_parent_workspace, _dispatch_read, _finish_tool,
    _monitor_tool, _read_tool, _run_parent, _tool,
)
from direct_evidence_diagnostic import FrozenEvidenceIndex, file_list_tool, text_search_tool
from scoped_decision_diagnostic import EvidenceRegistry


PROTOCOL_ID = "decision-discriminating-selector-v1"
MODES = ("counterfactual_observation", "decision_frontier")
SELECT_ACTION_TOOL = "select_investigation_action"
NESTED_TOOL_NAMES = {"file_read", "file_list", "text_search"}


def _selector_action_tool() -> dict[str, Any]:
    return _tool(
        SELECT_ACTION_TOOL,
        "Bind one requirement or claim and two contrasting expected observations to exactly "
        "one immediately executable frozen-evidence action. This records a selection; it does "
        "not decide task correctness.",
        {
            "premise": {
                "type": "string",
                "description": "Optional unless the current role explicitly requires it.",
            },
            "requirement_or_claim_being_tested": {"type": "string"},
            "outcome_if_supported": {"type": "string"},
            "outcome_if_violated": {"type": "string"},
            "action": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string", "enum": sorted(NESTED_TOOL_NAMES)},
                    "arguments": {"type": "object"},
                },
                "required": ["tool", "arguments"],
            },
        },
        ("requirement_or_claim_being_tested", "outcome_if_supported",
         "outcome_if_violated", "action"),
    )


def selector_spec(*, mode: str, parent_system: str, original_task: str,
                  decision_scope: str, index: FrozenEvidenceIndex,
                  remaining_calls: int) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"unknown discriminating-selector mode: {mode}")
    common = (
        "Select exactly one immediately executable investigation action. Bind it to a specific "
        "requirement or claim and state two genuinely different observable outcomes: one that "
        "would support it and one that would show it is violated. The selected action must be "
        "capable of observing that difference. Call select_investigation_action exactly once; "
        "do not decide the task, emit free-text instead, or invent a defect. This call consumes "
        "budget even if the protocol is invalid."
    )
    if mode == "decision_frontier":
        distinction = (
            " Also provide premise: one concrete currently unresolved premise whose truth or "
            "falsity could change the present root-completion decision. The tested requirement "
            "and action must serve that premise."
        )
    else:
        distinction = (
            " Choose whichever requirement or claim is worth testing. Omit premise; this role "
            "does not add a separate decision-frontier field."
        )
    descriptor = index.descriptor()
    view = {
        "decision_scope": decision_scope,
        "original_task": original_task,
        "remaining_total_calls_before_selection": remaining_calls,
        "frozen_query_scope": {
            "scope": descriptor["scope"],
            "checkpoint_version": descriptor["checkpoint_version"],
            "indexed_files": descriptor["indexed_files"],
        },
        "context_policy": "The complete restored parent History is available in this session.",
    }
    return {
        "system": parent_system.rstrip() + "\n\nBounded investigation-selection role: "
                  + common + distinction,
        "prompt": json.dumps(view, ensure_ascii=False, indent=2),
        "tools": [_selector_action_tool()],
    }


def _nonempty(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _integer(value: Any, name: str, lower: int, upper: int) -> None:
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"{name} must be an integer between {lower} and {upper}")


def _validate_nested_arguments(tool: str, arguments: dict[str, Any]) -> None:
    if tool == "file_read":
        allowed = {"path", "start", "count", "tail", "offset", "max_chars"}
        if set(arguments) - allowed:
            raise ValueError("file_read contains unknown arguments")
        _nonempty(arguments, "path")
        if "start" in arguments:
            _integer(arguments["start"], "start", 1, 2**31 - 1)
        if "count" in arguments:
            _integer(arguments["count"], "count", 1, 1000)
        if "tail" in arguments and type(arguments["tail"]) is not bool:
            raise ValueError("tail must be boolean")
        if arguments.get("tail") and "start" in arguments:
            raise ValueError("with tail=true omit start")
        if "offset" in arguments:
            _integer(arguments["offset"], "offset", 0, 2**31 - 1)
        if arguments.get("tail") and arguments.get("offset", 0):
            raise ValueError("omit offset with tail=true")
        if "max_chars" in arguments:
            _integer(arguments["max_chars"], "max_chars", 1, 200000)
        return
    if tool == "file_list":
        allowed = {"path", "recursive", "name_contains", "max_results"}
        if set(arguments) - allowed:
            raise ValueError("file_list contains unknown arguments")
        if "path" in arguments and not isinstance(arguments["path"], str):
            raise ValueError("path must be a string")
        if "recursive" in arguments and type(arguments["recursive"]) is not bool:
            raise ValueError("recursive must be boolean")
        if "name_contains" in arguments and not isinstance(arguments["name_contains"], str):
            raise ValueError("name_contains must be a string")
        if "max_results" in arguments:
            _integer(arguments["max_results"], "max_results", 1, 500)
        return
    if tool == "text_search":
        allowed = {"query", "path", "file_pattern", "case_sensitive", "max_results"}
        if set(arguments) - allowed:
            raise ValueError("text_search contains unknown arguments")
        query = _nonempty(arguments, "query")
        if len(query) > 500:
            raise ValueError("query must contain at most 500 characters")
        for name in ("path", "file_pattern"):
            if name in arguments and not isinstance(arguments[name], str):
                raise ValueError(f"{name} must be a string")
        if "case_sensitive" in arguments and type(arguments["case_sensitive"]) is not bool:
            raise ValueError("case_sensitive must be boolean")
        if "max_results" in arguments:
            _integer(arguments["max_results"], "max_results", 1, 200)
        return
    raise ValueError("illegal nested selector tool")


def _selection_result(*, research_record: dict[str, Any],
                      model_visible: dict[str, Any]) -> dict[str, Any]:
    return {"research_record": research_record, "model_visible": model_visible}


def _protocol_failure(condition: str, error: str, **research: Any) -> dict[str, Any]:
    return _selection_result(
        research_record={"condition": condition, **research},
        model_visible={"status": "selector_protocol_failure", "error": error},
    )


def execute_selection(*, response, mode: str, research_condition: str,
                      workspace: MonitorWorkspace, public_allowed: set[str],
                      index: FrozenEvidenceIndex) -> dict[str, Any]:
    calls = list(response.tool_calls or ())
    if len(calls) != 1:
        return _protocol_failure(
            research_condition, "selector must return exactly one structured action call",
            tool_call_count=len(calls))
    call = calls[0]
    if call.name != SELECT_ACTION_TOOL:
        return _protocol_failure(
            research_condition, "selector used an illegal protocol tool", selected_tool=call.name)
    try:
        payload = json.loads(call.arguments or "{}")
        if not isinstance(payload, dict):
            raise ValueError("selector action payload must be an object")
        allowed_outer = {"premise", "requirement_or_claim_being_tested",
                         "outcome_if_supported", "outcome_if_violated", "action"}
        if set(payload) - allowed_outer:
            raise ValueError("selector action contains unknown fields")
        requirement = _nonempty(payload, "requirement_or_claim_being_tested")
        supported = _nonempty(payload, "outcome_if_supported")
        violated = _nonempty(payload, "outcome_if_violated")
        premise = payload.get("premise")
        if mode == "decision_frontier":
            premise = _nonempty(payload, "premise")
        elif premise not in (None, ""):
            raise ValueError("premise must be omitted in this selector role")
        action = payload.get("action")
        if not isinstance(action, dict) or set(action) != {"tool", "arguments"}:
            raise ValueError("action must contain exactly tool and arguments")
        tool = action.get("tool")
        arguments = action.get("arguments")
        if tool not in NESTED_TOOL_NAMES:
            raise ValueError("illegal nested selector tool")
        if not isinstance(arguments, dict):
            raise ValueError("nested tool arguments must be an object")
        _validate_nested_arguments(tool, arguments)
    except (json.JSONDecodeError, ValueError) as exc:
        return _protocol_failure(research_condition, str(exc), selected_tool=call.name)

    outcome = index.dispatch(workspace, tool, arguments)
    if outcome is None:
        outcome = _dispatch_read(workspace, public_allowed, tool, arguments)
    if outcome is None:
        outcome = ToolOutcome({"status": "error", "error": "selected action is unavailable"})
    descriptor = index.descriptor()
    semantics = {
        "requirement_or_claim_being_tested": requirement,
        "outcome_if_supported": supported,
        "outcome_if_violated": violated,
    }
    if mode == "decision_frontier":
        semantics["premise"] = premise
    return _selection_result(
        research_record={
            "condition": research_condition,
            "mode": mode,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "selected_tool": tool,
        },
        model_visible={
            "status": "executed",
            "selection_semantics": semantics,
            "tool": tool,
            "arguments": arguments,
            "query_scope": {
                "scope": descriptor["scope"],
                "checkpoint_version": descriptor["checkpoint_version"],
                "indexed_files": descriptor["indexed_files"],
            },
            "raw_receipt": outcome.data,
        },
    )


def run_candidate(*, mode: str, research_condition: str, selector_client, parent_client,
                  branch_identity: str, seed_workspace: MonitorWorkspace,
                  branch_private_root: Path, index: FrozenEvidenceIndex,
                  initial_paths: tuple[str, ...], parent_history: list[dict[str, Any]],
                  parent_system: str, original_task: str, decision_scope: str,
                  acceptance_question: str, total_calls: int = 6,
                  audit: Callable[..., None] | None = None) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"unknown discriminating-selector mode: {mode}")
    if total_calls != 6:
        raise ValueError("the selector protocol freezes the total budget at six calls")
    budget = CallBudget(total_calls)
    workspace = _clone_parent_workspace(
        seed_workspace, Path(branch_private_root) / branch_identity)
    allowed = {str(path).replace("\\", "/") for path in initial_paths}
    spec = selector_spec(
        mode=mode, parent_system=parent_system, original_task=original_task,
        decision_scope=decision_scope, index=index, remaining_calls=budget.remaining)
    selector_client.restore_history(parent_history)
    budget.consume()
    response = selector_client.complete(
        [{"role": "system", "content": spec["system"]},
         {"role": "user", "content": spec["prompt"]}], spec["tools"])
    observation = execute_selection(
        response=response, mode=mode, research_condition=research_condition,
        workspace=workspace, public_allowed=allowed, index=index)
    if audit:
        audit("discriminating_selector_observation", budget_used=budget.used,
              research=observation["research_record"],
              model_visible=observation["model_visible"])

    parent_client.restore_history(parent_history)
    parent_prompt = (
        acceptance_question + "\n\nA one-call investigation selector produced the following "
        "current observation. Its premise and contrasting outcomes are proposals from the "
        "selector, not established facts. The tool receipt is real current evidence, but "
        "executing it does not by itself prove correctness:\n\n" +
        json.dumps(observation["model_visible"], ensure_ascii=False, indent=2) +
        f"\n\nProtocol budget: {budget.remaining} logical calls remain for investigation and "
        "the final parent decision."
    )
    parent_tools = [_read_tool(), file_list_tool(), text_search_tool(),
                    _monitor_tool("file_write"), _monitor_tool("file_patch"), _finish_tool()]
    registry = EvidenceRegistry(parent_history)
    action = _run_parent(
        parent_client, parent_system, parent_prompt, parent_tools, workspace, allowed,
        budget, budget.remaining, "finish_parent_decision", audit=audit,
        restore_private_maintenance=True,
        extra_dispatch=lambda name, args: index.dispatch(workspace, name, args),
        receipt_protocol=PROTOCOL_ID, evidence_decorator=registry.decorate,
    )
    payload = action.payload if isinstance(action.payload, dict) else {}
    return {
        "protocol": PROTOCOL_ID,
        "condition": research_condition,
        "mode": mode,
        "status": "completed" if action.kind == "finish_parent_decision" else "incomplete",
        "selection_observation": observation,
        "parent_action": action.kind,
        "outcome": payload.get("outcome"),
        "conclusion": payload.get("conclusion"),
        "calls": budget.used,
    }
