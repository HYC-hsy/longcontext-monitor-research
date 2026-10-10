"""Static C02 control through deployed MonitorAgent, run_review, CRS, RHR and RER."""

from __future__ import annotations

import json
import hashlib
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .bootstrap import HANDOFF, HISTORIC_REVIEW_ID, prepare_agent
from .freeze_inputs import NEW
from .payload_client import BoundaryClient, BridgeIntegrityError
from .ports import IsolatedAnalysis, NoTaskControl
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.docker_tool import DockerToolPort
from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.loop import MonitorLoopError, run_review
from monitor_agent_core.provider import HistoryCapacityError, ProviderRecoveryExhausted
from monitor_agent_core.handoff_validation import ContinuationContractError
from monitor_agent_core.runtime import _remaining_root_turns
from monitor_agent_core.actions import ToolOutcome
from jsonschema import Draft7Validator
import requests


ROOT_CEILING = 300


def _failure_types(exc):
    chain, cursor = [], exc
    while cursor is not None and len(chain) < 16:
        chain.append(type(cursor).__name__)
        cursor = cursor.__cause__ or cursor.__context__
    return chain


def _native_undecided(exc, client, analysis):
    """A maintenance/capacity wrapper cannot conceal a later transport fault."""
    if client.failure_latch or getattr(analysis, "integrity_error", None) is not None:
        return False
    cursor = exc
    while cursor is not None:
        if isinstance(cursor, (BridgeIntegrityError, requests.RequestException, OSError)):
            return False
        cursor = cursor.__cause__ or cursor.__context__
    chain = _failure_types(exc)
    return ("HistoryCapacityError" in chain or
            "ContinuationContractError" in chain)


class BoundaryMonitorAgent(MonitorAgent):
    def dispatch(self, name, arguments):
        failure = getattr(self.analysis, "integrity_error", None)
        if failure is not None:
            raise BridgeIntegrityError("Isolated analysis integrity failure") from failure
        if name not in {"wait", "intervene", "allow_complete"}:
            schema = next((tool["input_schema"] for tool in self.client.frozen["tools"]
                           if tool["name"] == name), None)
            if schema is None:
                return ToolOutcome({"status": "error", "error": "Unknown ordinary tool"})
            errors = sorted(Draft7Validator(schema).iter_errors(arguments), key=lambda e: str(e.path))
            if errors:
                return ToolOutcome({"status": "error", "error": "Invalid tool parameters: " +
                                    errors[0].message[:500]})
        result = super().dispatch(name, arguments)
        failure = getattr(self.analysis, "integrity_error", None)
        if failure is not None:
            raise BridgeIntegrityError("Isolated analysis integrity failure") from failure
        return result

    def _archive_rer_branch(self, reason):
        if self._rer_parent_history is None:
            return
        branch = self.client.export_history()
        raw = json.dumps(branch, ensure_ascii=False).encode("utf-8")
        location = (self.workspace.private_root / "audit" / "rer_branches" /
                    f"{self.review_id}-frame{self._rer_frame_sequence}-{uuid.uuid4().hex}.json")
        location.parent.mkdir(parents=True, exist_ok=True)
        with location.open("xb") as stream:
            stream.write(raw)
        self._audit_dialogue("research_rer_branch_archived", path="monitor/" +
                             location.relative_to(self.workspace.private_root).as_posix(),
                             reason=reason, frame_sequence=self._rer_frame_sequence,
                             sha256=hashlib.sha256(raw).hexdigest(),
                             history=self.client.history_measure(),
                             provider_request_count=self.client.send_count)

    def enter_root_reestimate(self, handoff, action):
        self._archive_rer_branch("rer_frame_restarted")
        return super().enter_root_reestimate(handoff, action)

    def restore_rer_parent(self, disposition):
        if self._rer_parent_history is not None:
            self._archive_rer_branch("rer_parent_restore:" + disposition)
            self.client.bridge_history_boundary = "rer_parent_restore"
        return super().restore_rer_parent(disposition)


def _record_telemetry(agent, telemetry):
    for name, key in (("provider_usage.jsonl", "usage"),
                      ("history_transforms.jsonl", "history_transforms"),
                      ("request_attempts.jsonl", "request_attempts")):
        for row in telemetry.get(key, []):
            agent.workspace.write_text("monitor/audit/" + name,
                                       json.dumps(row, ensure_ascii=False) + "\n", mode="append")


def _close_first_review(agent, action, error=None):
    disposition = ("review_exhausted" if isinstance(error, MonitorLoopError) else
                   "error" if error is not None else
                   "root_reestimate" if action is not None and action.kind == "root_reestimate"
                   else "review_ended")
    agent.dcm.end_review(disposition)
    agent.situation.end_review(action)
    agent._progress("review_finished", action=action.kind if action else None,
                    frame=agent.frame_kind, handoff=agent.root_frame_handoff)
    agent.workspace.write_text("monitor/audit/reviews.jsonl", json.dumps({
        "action": asdict(action) if action else None, "frame": agent.frame_kind,
        "handoff": agent.root_frame_handoff, "disposition": disposition,
        "bootstrap_historical_review": True}, ensure_ascii=False) + "\n", mode="append")
    _record_telemetry(agent, agent.client.drain_telemetry())
    if error is not None or action is None or action.kind != "root_reestimate":
        agent.restore_rer_parent("error" if error is not None else
                                 action.kind if action is not None else "incomplete")
    agent._leave_root_frame()
    agent.workspace.write_text("monitor/audit/provider_history.json",
                               json.dumps(agent.client.export_history(), ensure_ascii=False),
                               mode="replace")


def _continue_historical_review(agent, frozen):
    """Continue native run_review at the historical pre-send cut, without another wake."""
    new_review_id = uuid.uuid4().hex
    if new_review_id == HISTORIC_REVIEW_ID:
        raise BridgeIntegrityError("Research review identity collided with historical review")
    agent.review_id = new_review_id
    agent.client.review_id = new_review_id
    agent.dcm.begin_review(new_review_id)
    agent.control_echo.begin_review(new_review_id)
    agent.situation.begin_review(new_review_id)
    agent._progress("review_started", completion_pending=True)
    agent._audit_dialogue("research_historical_review_continued",
                          historical_review_id=HISTORIC_REVIEW_ID,
                          research_review_id=new_review_id,
                          historical_tool_result_message_sha256=agent.client.history_measure()["sha256"])
    action, error = None, None
    try:
        # The first provider call uses the already-restored final user/tool
        # result message. BoundaryClient ignores run_review's synthetic wake
        # only for this one call, and compares the actual transport payload.
        native_system = frozen["system"][:-(len(NEW) + 2)]
        action = run_review(agent.client, native_system, "", _tools(frozen),
                            agent.dispatch, ROOT_CEILING, audit=agent._audit_dialogue,
                            before_model=agent._refresh_review_context)
        if agent.control_echo is not None:
            agent.control_echo.complete_review(action)
        return action
    except Exception as exc:
        error = exc
        raise
    finally:
        _close_first_review(agent, action, error)


def _tools(frozen):
    return [{"type": "function", "function": {"name": row["name"],
            "description": row["description"], "parameters": row["input_schema"]}}
            for row in frozen["tools"]]


def run_native_slot(fixture: Path, frozen: dict, profile: dict, audit, session):
    client = BoundaryClient(profile, frozen, audit, session)
    agent = prepare_agent(fixture, frozen, client, BoundaryMonitorAgent)
    def delivered_historical_context():
        agent.situation.shown_cursor = HANDOFF["cursor"]
        agent.situation.shown_this_review = True
        audit.record("historical_active_context_injected", request_index=1,
                     request_sha256=client.first_request_sha256,
                     review_id=agent.review_id)
    client.first_context_delivered = delivered_historical_context
    port = DockerToolPort(fixture)
    analysis = IsolatedAnalysis(port, audit)
    agent.analysis = analysis
    control = NoTaskControl(audit, HANDOFF)
    agent.intervention_callback = control.submit_intervention
    started = time.monotonic()
    result = {"terminal": None, "error_type": None, "root_subreviews": [],
              "root_turn_ceiling": ROOT_CEILING}
    primary_error = None
    try:
        used_before = client.complete_calls
        try:
            action = _continue_historical_review(agent, frozen)
        except MonitorLoopError:
            result["terminal"] = "valid_capped_no_terminal"
            return result
        used = client.complete_calls - used_before
        result["root_subreviews"].append({"kind": "historical_continuation",
                                          "model_cycles": used})
        remaining = ROOT_CEILING - used
        while action.kind == "root_reestimate":
            if remaining <= 0:
                agent.crs.abandon("root_turn_budget_exhausted")
                agent.restore_rer_parent("root_turn_budget_exhausted")
                result["terminal"] = "valid_capped_no_terminal"
                return result
            if agent.completion_state() != HANDOFF:
                agent.crs.abandon("stale_handoff")
                agent.restore_rer_parent("stale_handoff")
                raise BridgeIntegrityError("Static handoff changed during root re-estimation")
            client.bridge_history_boundary = "rer_fresh_branch"
            agent.enter_root_reestimate(HANDOFF, action)
            before = client.complete_calls
            try:
                action = agent.review("", completion_pending=True, root_handoff=HANDOFF,
                                      max_turns_override=remaining)
            except MonitorLoopError:
                result["terminal"] = "valid_capped_no_terminal"
                return result
            consumed = client.complete_calls - before
            if action.kind == "root_reestimate":
                native_remaining = _remaining_root_turns(remaining, action)
                if native_remaining != remaining - consumed:
                    raise BridgeIntegrityError("Native root-turn charge differs from complete count")
            result["root_subreviews"].append({"kind": "rer_root_review",
                                              "model_cycles": consumed,
                                              "review_id": agent.review_id})
            remaining -= consumed
        if action.kind == "allow_complete":
            control.final_release(action, agent.completion_state())
            result["terminal"] = "final_release_eligible"
        elif action.kind == "root_intervened":
            result["terminal"] = "static_root_intervention"
        else:
            raise BridgeIntegrityError(f"Unexpected static root action: {action.kind}")
        result["action"] = asdict(action)
        return result
    except (HistoryCapacityError, ContinuationContractError, ProviderRecoveryExhausted) as exc:
        chain = _failure_types(exc)
        if _native_undecided(exc, client, analysis):
            result["terminal"] = "undecided_native_maintenance_or_capacity"
            result["error_type"] = type(exc).__name__
            result["cause_types"] = chain
            audit.record("native_undecided", reason_type=type(exc).__name__, cause_types=chain)
            return result
        primary_error = exc
        result["terminal"] = "infrastructure_or_protocol_failure"
        result["error_type"] = type(exc).__name__
        result["cause_types"] = chain
        raise
    except Exception as exc:
        primary_error = exc
        result["terminal"] = "infrastructure_or_protocol_failure"
        result["error_type"] = type(exc).__name__
        raise
    finally:
        restore_error = None
        if agent._rer_parent_history is not None:
            try:
                agent.crs.abandon("runtime_error" if primary_error else "static_exit")
                agent.restore_rer_parent("runtime_error" if primary_error else "static_exit")
            except Exception as exc:
                restore_error = exc
                audit.record("rer_restore_failure", error_type=type(exc).__name__,
                             prior_error_type=type(primary_error).__name__ if primary_error else None)
        cleanup_error = None
        try:
            analysis.close()
        except Exception as cleanup_exc:
            cleanup_error = cleanup_exc
            audit.record("cleanup_failure", error_type=type(cleanup_exc).__name__,
                         prior_error_type=type(primary_error).__name__ if primary_error else None)
        result.update(provider_requests=client.send_count,
                      accepted_responses=client.accepted_count,
                      outer_model_cycles=client.complete_calls,
                      wall_seconds=time.monotonic() - started,
                      cleanup_error_type=type(cleanup_error).__name__ if cleanup_error else None,
                      restore_error_type=type(restore_error).__name__ if restore_error else None)
        if (cleanup_error is not None or restore_error is not None) and primary_error is None:
            result["terminal"] = "infrastructure_or_protocol_failure"
        (audit.root / "result.json").write_text(json.dumps(result, ensure_ascii=False,
                                                            indent=2), encoding="utf-8")
        if primary_error is None and (restore_error is not None or cleanup_error is not None):
            raise BridgeIntegrityError("Per-slot RER restore or cleanup failed") from (
                restore_error or cleanup_error)
