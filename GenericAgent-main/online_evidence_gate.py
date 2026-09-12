"""Public-event semantic frontend feeding the deterministic completion kernel."""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

from completion_contract import CompletionContract
from evidence_completion_kernel import EvidenceCompletionKernel
from evidence_state import EvidenceCarryingState, OBSERVATION_SCHEMA
from evidence_lineage import InterventionRef, build_lineage_proposal
from research_runtime import CompletionDecision, emit


MUTATION_TOOLS = frozenset({"file_write", "file_patch"})


def inert_json_tool(api_mode: str, name: str) -> list[dict[str, Any]]:
    definition = {
        "name": name, "description": "Do not call; return JSON as text.",
        "parameters": {"type": "object", "properties": {}},
    }
    if api_mode == "responses":
        return [{"type": "function", "function": definition}]
    return [{
        "name": definition["name"], "description": definition["description"],
        "input_schema": definition["parameters"],
    }]


def _parse_json(text: str) -> Mapping[str, Any]:
    stripped = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        if start < 0:
            raise
        value, _ = json.JSONDecoder().raw_decode(stripped[start:])
    if not isinstance(value, Mapping):
        raise ValueError("Online evidence response must be an object")
    if not isinstance(value.get("changes"), list) or not isinstance(value.get("observations"), list):
        raise ValueError("Online evidence response needs changes and observations")
    return value


class OnlineEvidenceCompletionGate:
    """Refresh typed state from public events only when completion is proposed."""

    def __init__(self, state: EvidenceCarryingState, contract: CompletionContract,
                 config_name: str, shadow_only: bool = False,
                 recovery_style: str = "flat"):
        self.state = state
        self.contract = contract
        self.config_name = config_name
        self.shadow_only = shadow_only
        self.kernel = EvidenceCompletionKernel(state, contract, recovery_style=recovery_style)
        self.events: list[dict[str, Any]] = []
        self._processed_event_count = 0
        self._call_count = 0
        self._interventions: list[InterventionRef] = []
        self.lineage: list[dict[str, Any]] = []
        self._mode_emitted = False

    def record_turn(self, tool_calls: list[Mapping[str, Any]],
                    tool_results: list[Mapping[str, Any]], turn: int) -> None:
        results = {str(item.get("tool_use_id", "")): item.get("content", "")
                   for item in tool_results}
        for call in tool_calls:
            name = str(call.get("tool_name", ""))
            if name == "no_tool":
                continue
            self.events.append({
                "event_id": f"live-tool-{len(self.events) + 1:05d}",
                "event_type": "tool_interaction", "turn": turn,
                "source_kind": "tool_result", "tool_name": name,
                "arguments": call.get("args", {}),
                "content": str(results.get(str(call.get("id", "")), ""))[:12000],
            })

    def _state_schema(self) -> dict[str, Any]:
        return {
            "task_id": self.state.task_id,
            "obligations": [{
                "obligation_id": item.obligation_id,
                "description": item.description,
                "version": item.version,
                "predicates": [{
                    "predicate_id": pred.specification.predicate_id,
                    "description": pred.specification.description,
                    "observable_by": list(pred.specification.observable_by),
                } for pred in item.predicates.values()],
            } for item in self.state.obligations.values()],
        }

    def _prompt(self, events: list[Mapping[str, Any]]) -> str:
        public = {
            "state_schema": self._state_schema(),
            "terminal_guards": [guard.__dict__ for guard in self.contract.guards],
            "new_public_events": events,
        }
        return """Update an evidence-carrying task state from PUBLIC Agent tool events.
You are a conservative semantic frontend, not a checker or whole-task success judge.

Rules:
1. Never invent obligations, predicates, events, paths, or hidden outcomes.
2. A change may cite only file_write/file_patch and only an obligation whose subject
   could be changed by a displayed path. Omit uncertain mappings.
3. A tool observation supports only behavior directly exercised by displayed arguments
   and result. Exit code alone is insufficient without relevant output.
4. Explicit contrary output uses contradicts. Ambiguous evidence is omitted.
5. Do not emit evidence before the latest cited change for that obligation.
6. Agent prose and completion claims are not tool evidence.
7. Return JSON only.

Schema:
{"changes":[{"source_event_id":"...","obligation_id":"...","changed_paths":["..."]}],"observations":[{"source_event_id":"...","obligation_id":"...","predicate_ids":["..."],"result":"supports|contradicts","content_ref":"...","warrant":"why the cited output supports exactly these predicates, or unknown","evidence_scope":"behavioral|structural|existence|unknown","independence_claim":"independent|dependent|unknown","independence_basis":["explicit public basis, or empty"]}]}

The four lineage fields are proposals for audit, not authoritative verdicts. Use unknown
when the displayed event does not establish them. Never call evidence independent merely
because it is a tool result or behavioral merely because a test exited successfully.

PUBLIC INPUT:
""" + json.dumps(public, ensure_ascii=False)

    def _call(self, events: list[Mapping[str, Any]]) -> Mapping[str, Any]:
        from llmcore import resolve_session

        session = resolve_session(self.config_name)
        if session is None:
            raise ValueError(f"Unsupported evidence frontend config: {self.config_name}")
        session.max_tokens = 12000
        session.tools = inert_json_tool(
            getattr(session, "api_mode", "messages"), "record_frontend_error"
        )
        raw = "".join(session.raw_ask([{
            "role": "user", "content": [{"type": "text", "text": self._prompt(events)}],
        }])).strip()
        if not raw or raw.startswith("!!!Error:"):
            raise RuntimeError(f"Online evidence frontend failed: {raw[:300] or '<empty>'}")
        self._call_count += 1
        return _parse_json(raw)

    def _apply(self, response: Mapping[str, Any],
               events: list[Mapping[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
        event_index = {item["event_id"]: (index, item) for index, item in enumerate(events)}
        latest_change: dict[str, int] = {}
        accepted_changes = accepted_observations = rejected = 0
        lineage: list[dict[str, Any]] = []
        for row in response["changes"]:
            pair = event_index.get(str(row.get("source_event_id", "")))
            obligation_id = str(row.get("obligation_id", ""))
            paths = [str(path) for path in row.get("changed_paths", []) if str(path).strip()]
            if (pair is None or pair[1].get("tool_name") not in MUTATION_TOOLS
                    or obligation_id not in self.state.obligations or not paths):
                rejected += 1
                continue
            displayed = json.dumps(pair[1].get("arguments", {}), ensure_ascii=False).lower()
            if any(path.lower() not in displayed for path in paths):
                rejected += 1
                continue
            latest_change[obligation_id] = max(pair[0], latest_change.get(obligation_id, -1))
        for obligation_id, index in sorted(latest_change.items(), key=lambda item: item[1]):
            self.state.advance_obligation_version(obligation_id, events[index]["event_id"])
            accepted_changes += 1
        for row in response["observations"]:
            event_id = str(row.get("source_event_id", ""))
            pair = event_index.get(event_id)
            obligation_id = str(row.get("obligation_id", ""))
            obligation = self.state.obligations.get(obligation_id)
            predicate_ids = list(dict.fromkeys(str(x) for x in row.get("predicate_ids", [])))
            result = str(row.get("result", ""))
            rejection_reason = None
            if pair is None:
                rejection_reason = "UNKNOWN_SOURCE_EVENT"
            elif obligation is None:
                rejection_reason = "UNKNOWN_OBLIGATION"
            elif not predicate_ids:
                rejection_reason = "EMPTY_PREDICATE_SET"
            elif pair[0] < latest_change.get(obligation_id, -1):
                rejection_reason = "PRE_VERSION_CHANGE_EVIDENCE"
            if rejection_reason:
                rejected += 1
                lineage.append(build_lineage_proposal(
                    row, pair[1] if pair else None, obligation.version if obligation else None,
                    self._interventions, accepted=False, rejection_reason=rejection_reason,
                ))
                continue
            known = obligation.predicates
            if set(predicate_ids) - set(known) or result not in {"supports", "contradicts"}:
                rejected += 1
                lineage.append(build_lineage_proposal(
                    row, pair[1], obligation.version, self._interventions,
                    accepted=False, rejection_reason="INVALID_PREDICATE_OR_RESULT",
                ))
                continue
            if any("tool_result" not in known[item].specification.observable_by
                   for item in predicate_ids):
                rejected += 1
                lineage.append(build_lineage_proposal(
                    row, pair[1], obligation.version, self._interventions,
                    accepted=False, rejection_reason="DISALLOWED_SOURCE_KIND",
                ))
                continue
            self.state.apply_observation({
                "schema_version": OBSERVATION_SCHEMA,
                "observation_id": f"live-frontend-{self._call_count:03d}-{accepted_observations + 1:04d}",
                "source_event_id": event_id, "source_kind": "tool_result",
                "obligation_id": obligation_id, "predicate_ids": predicate_ids,
                "result": result, "subject_version": obligation.version,
                "content_ref": str(row.get("content_ref", "public event"))[:1000],
                "observed_at": f"completion-refresh-{self._call_count}",
            })
            lineage.append(build_lineage_proposal(
                row, pair[1], obligation.version, self._interventions,
                accepted=True,
            ))
            accepted_observations += 1
        return ({"changes": accepted_changes, "observations": accepted_observations,
                 "rejected": rejected}, lineage)

    def prepare(self, proposal: Any) -> CompletionDecision | None:
        """Refresh public state once, before the completion-policy checkpoint."""
        if not self._mode_emitted:
            emit("online_evidence_gate_mode", {
                "mode": "lineage_shadow" if self.shadow_only else "active",
                "shadow_only": self.shadow_only,
                "recovery_style": self.kernel.recovery_style,
            })
            self._mode_emitted = True
        new_events = self.events[self._processed_event_count:]
        if new_events:
            try:
                counts, lineage = self._apply(self._call(new_events), new_events)
                self._processed_event_count = len(self.events)
                emit("online_evidence_refresh", {
                    **counts, "public_event_count": len(new_events),
                    "frontend_calls": self._call_count,
                })
                emit("online_evidence_lineage", {
                    "schema_version": "online-evidence-lineage-batch/0",
                    "proposal_count": len(lineage), "proposals": lineage,
                })
                self.lineage.extend(lineage)
            except Exception as exc:
                emit("online_evidence_refresh_error", {
                    "error_type": type(exc).__name__, "message": str(exc)[:500],
                })
                decision = CompletionDecision(
                    decision="ABSTAIN", reason_codes=("EVIDENCE_FRONTEND_ERROR",),
                )
                self._record_intervention(proposal, decision)
                return decision
        return None

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": "online-evidence-gate-state/0",
            "evidence_state": self.state.snapshot(),
            "events": list(self.events),
            "processed_event_count": self._processed_event_count,
            "frontend_call_count": self._call_count,
            "interventions": [item.__dict__ for item in self._interventions],
            "lineage": list(self.lineage),
            "shadow_only": self.shadow_only,
            "recovery_style": self.kernel.recovery_style,
        }

    def restore_snapshot(self, value: Mapping[str, Any]) -> None:
        if value.get("schema_version") != "online-evidence-gate-state/0":
            raise ValueError("Unsupported online evidence gate snapshot")
        self.state = EvidenceCarryingState.from_snapshot(value["evidence_state"])
        self.kernel.state = self.state
        self.events = list(value.get("events", []))
        self._processed_event_count = int(value.get("processed_event_count", 0))
        self._call_count = int(value.get("frontend_call_count", 0))
        self._interventions = [InterventionRef(**item) for item in value.get("interventions", [])]
        self.lineage = list(value.get("lineage", []))
        self._mode_emitted = False

    def decide(self, proposal: Any) -> CompletionDecision:
        prepared_error = self.prepare(proposal)
        if prepared_error is not None:
            return prepared_error
        decision = self.kernel.decide(proposal)
        if self.shadow_only:
            emit("completion_shadow_decision", {
                **decision.as_payload(),
                "proposal_id": str(getattr(proposal, "proposal_id", "unknown")),
                "active_decision": "ALLOW_COMPLETE",
            })
            return CompletionDecision(
                decision="ALLOW_COMPLETE", reason_codes=("SHADOW_ONLY_NO_INTERVENTION",),
            )
        self._record_intervention(proposal, decision)
        return decision

    def _record_intervention(self, proposal: Any, decision: CompletionDecision) -> None:
        if decision.decision == "ALLOW_COMPLETE":
            return
        self._interventions.append(InterventionRef(
            event_id=str(getattr(proposal, "proposal_id", f"proposal-{len(self._interventions) + 1}")),
            turn=int(getattr(proposal, "turn", 0)), decision=decision.decision,
        ))

    __call__ = decide
