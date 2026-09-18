"""Minimal parent-selected-question plus independent-C experiment.

This module is deliberately separate from the online monitor and from the
existing C/D panel runner.  It shares the provider, workspace, tool loop and
IndependentVerifier, but gives the parent and child a common call budget.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from monitor_agent_core.actions import MonitorAction, ToolOutcome
from monitor_agent_core.loop import MonitorLoopError, run_review
from monitor_agent_core.probe import IndependentVerifier, ProbeConfig, ProbeBudgetExceeded
from monitor_agent_core.workspace import MonitorWorkspace


@dataclass(frozen=True)
class SelectionConfig:
    total_calls: int = 6
    selection_turns: int = 2
    child_turns: int = 4
    final_turns: int = 2


class SharedCallBudget:
    def __init__(self, limit: int):
        if limit < 3:
            raise ValueError("total_calls must reserve selection, child and final calls")
        self.limit = limit
        self.used = 0

    @property
    def remaining(self) -> int:
        return self.limit - self.used

    def consume(self) -> None:
        if self.used >= self.limit:
            raise ProbeBudgetExceeded("shared experiment budget exhausted")
        self.used += 1


def _tool(name: str, description: str, properties: dict[str, Any], required=()):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": list(required)},
    }}


def _file_read_tool():
    return _tool("file_read", "Read one permitted task or workspace file.", {
        "path": {"type": "string"}, "start": {"type": "integer"},
        "count": {"type": "integer"}, "tail": {"type": "boolean"},
        "offset": {"type": "integer", "minimum": 0},
        "max_chars": {"type": "integer", "minimum": 1, "maximum": 200000},
    })


def _dispatch_read(workspace, allowed: set[str], name: str, arguments: dict[str, Any]):
    if name != "file_read":
        return None
    path = str(arguments.get("path", "")).replace("\\", "/")
    if path not in allowed:
        return ToolOutcome({"status": "error", "error": "path is outside this experiment"})
    return ToolOutcome(workspace.read_text(
        path, arguments.get("start", 1), arguments.get("count", 200),
        tail=arguments.get("tail", False), offset=arguments.get("offset", 0),
        max_chars=arguments.get("max_chars", 20000),
    ))


def _selection_tools():
    return [_file_read_tool(), _tool(
        "select_local_question",
        "Select one concise question whose answer could change the current acceptance decision. "
        "Do not name a file unless the evidence you already read makes it necessary.",
        {"question": {"type": "string"}, "reason": {"type": "string"}},
        ("question", "reason"),
    )]


def _final_tools():
    return [_tool(
        "finalize_parent_decision",
        "Return the parent's final scoped decision after considering the local verifier result. "
        "The conclusion must state what the evidence supports and any remaining limitation.",
        {"outcome": {"type": "string", "enum": [
            "supported_in_scope", "contradicted", "unresolved"]},
         "conclusion": {"type": "string"}},
        ("outcome", "conclusion"),
    )]


def _budgeted_complete(client, budget: SharedCallBudget):
    original = client.complete

    def complete(messages, tools):
        budget.consume()
        return original(messages, tools)

    client.complete = complete
    return original


def _run_parent_phase(client, system: str, prompt: str, tools, workspace,
                      allowed: set[str], budget: SharedCallBudget,
                      max_turns: int, audit, action_name: str):
    original = _budgeted_complete(client, budget)
    try:
        def dispatch(name, args):
            read = _dispatch_read(workspace, allowed, name, args)
            if read is not None:
                return read
            if name == action_name:
                if action_name == "select_local_question":
                    value = str(args.get("question", "")).strip()
                    if not value:
                        return ToolOutcome({"status": "error", "error": "question is required"})
                    return ToolOutcome(None, action=MonitorAction(action_name, {
                        "question": value, "reason": str(args.get("reason", "")).strip()}))
                conclusion = str(args.get("conclusion", "")).strip()
                outcome = args.get("outcome")
                if outcome not in {"supported_in_scope", "contradicted", "unresolved"} or not conclusion:
                    return ToolOutcome({"status": "error", "error": "explicit outcome and conclusion required"})
                return ToolOutcome(None, action=MonitorAction(action_name, {
                    "outcome": outcome, "conclusion": conclusion}))
            return ToolOutcome({"status": "error", "error": f"unknown parent tool: {name}"})
        return run_review(
            client, system, prompt, tools,
            dispatch,
            max_turns=max_turns, audit=audit,
        )
    except (ProbeBudgetExceeded, MonitorLoopError) as exc:
        return MonitorAction("parent_phase_incomplete", {"reason": type(exc).__name__})
    finally:
        client.complete = original


def run_autonomous_selection_case(parent_client, child_client, workspace,
                                  question: str, source_paths: tuple[str, ...],
                                  evidence_paths: tuple[str, ...],
                                  config: SelectionConfig = SelectionConfig(),
                                  audit=None) -> dict[str, Any]:
    """Run selection -> isolated C -> parent decision under one budget."""
    allowed = {str(p).replace("\\", "/") for p in source_paths + evidence_paths}
    budget = SharedCallBudget(config.total_calls)
    record = audit or (lambda event, **fields: None)
    parent_system = (
        "You are the parent Supervisor deciding whether the implementation can be accepted. "
        "Inspect only the permitted materials. Before deciding, select one local question "
        "whose answer could materially change the decision. Do not assume a checker or hidden "
        "answer, and do not invent a defect."
    )
    selection = _run_parent_phase(
        parent_client, parent_system,
        question + "\n\nChoose the most decision-relevant local uncertainty before any final decision.",
        _selection_tools(), workspace, allowed, budget, config.selection_turns, record,
        "select_local_question")
    if selection.kind != "select_local_question":
        return {"status": "incomplete", "stage": "selection", "budget_used": budget.used}

    selected = selection.payload
    child_calls = max(1, min(config.child_turns, budget.remaining - 1))
    child = IndependentVerifier(
        child_client, workspace,
        ProbeConfig(
            mode="direct", source_paths=source_paths,
            evidence_paths=evidence_paths, max_requests=child_calls,
            max_turns=config.child_turns,
        ),
        audit=record,
    )
    child_result = child.run(str(selected["question"]))
    budget.used += child.logical_calls
    if budget.remaining < 1:
        return {"status": "incomplete", "stage": "final", "selection": selected,
                "child": child_result, "budget_used": budget.used}

    final_prompt = (
        f"Original acceptance question:\n{question}\n\n"
        f"You selected this local question:\n{selected['question']}\n"
        f"Selection reason:\n{selected.get('reason', '')}\n\n"
        "The independent C verifier returned this scoped result:\n" +
        json.dumps({"status": child_result.status, "outcome": child_result.outcome,
                    "conclusion": child_result.conclusion,
                    "limitation": child_result.limitation}, ensure_ascii=False) +
        "\n\nNow make the parent decision. Do not treat an unfinished verifier as a cautious success."
    )
    final_system = (
        "You are the parent Supervisor completing one acceptance decision. Use the selected "
        "question and the independent verifier's scoped result, preserving uncertainty and "
        "avoiding claims broader than the evidence."
    )
    final = _run_parent_phase(
        parent_client, final_system, final_prompt, _final_tools(), workspace, allowed,
        budget, config.final_turns, record, "finalize_parent_decision")
    if final.kind != "finalize_parent_decision":
        return {"status": "incomplete", "stage": "final", "selection": selected,
                "child": child_result, "budget_used": budget.used}
    return {"status": "completed", "selection": selected, "child": child_result,
            "final": final.payload, "budget_used": budget.used}
