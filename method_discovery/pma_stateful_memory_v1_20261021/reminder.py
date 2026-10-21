"""Strict selection, host-derived anchors and one-shot auxiliary Task input."""

from __future__ import annotations

from copy import deepcopy
from typing import Callable

from .source import ContractError, canonical, digest, fields, nonempty


def _selected(snapshot: dict, ref: dict) -> tuple[dict, str, str]:
    belief = snapshot["B"]
    if ref["type"] == "state":
        fields(ref, {"type", "record_id", "revision"})
        item = next((item for item in belief["W"]["states"] if item["record_id"] ==
                     ref["record_id"] and item["revision"] == ref["revision"]), None)
        if item is None or item["use_status"] == "retracted":
            raise ContractError("selection_stale_or_retracted_ref")
        if item["kind"] == "knowledge":
            return item, item["claim"]["text"], "claim"
        episode = item["episode"]
        text = (f"Past episode: {episode['conditions']['text']}; "
                f"action: {episode['action_text']}; result: {episode['result']['text']}")
        return item, text, "episode"
    if ref["type"] == "requirement":
        fields(ref, {"type", "requirement_id", "revision", "task_version"})
        item = next((item for item in belief["G"]["specifications"] if
                     item["requirement_id"] == ref["requirement_id"] and
                     item["revision"] == ref["revision"] and
                     item["task_version"] == ref["task_version"]), None)
        if item is None or item["status"] != "active":
            raise ContractError("selection_stale_or_retired_ref")
        return item, item["interpretation"], "requirement"
    if ref["type"] == "gap":
        fields(ref, {"type", "gap_id", "revision", "task_version"})
        item = next((item for item in belief["DeltaE"] + belief["DeltaA"] if
                     item["gap_id"] == ref["gap_id"] and
                     item["revision"] == ref["revision"] and
                     item["task_version"] == ref["task_version"]), None)
        if item is None:
            raise ContractError("selection_stale_ref")
        return item, f"{item['target']}: {item['reason']}", "gap"
    raise ContractError("selection_invalid_ref_type")


def validate_selection(raw: object, *, snapshot: dict, phase2_view_id: str,
                       selected_refs: list[dict]) -> dict:
    if type(raw) is not dict or raw.get("decision") not in {"silent", "remind"}:
        raise ContractError("selection_malformed")
    required = ({"decision", "state_version", "task_version", "phase2_view_id"}
                if raw["decision"] == "silent" else
                {"decision", "state_version", "task_version", "phase2_view_id",
                 "refs", "context_for_action"})
    decision = fields(raw, required)
    if (decision["state_version"] != snapshot["state_version"] or
            decision["task_version"] != snapshot["B"]["G"]["task_version"] or
            decision["phase2_view_id"] != phase2_view_id):
        raise ContractError("selection_binding_mismatch")
    if decision["decision"] == "silent":
        return decision
    refs = decision["refs"]
    if type(refs) is not list or not 1 <= len(refs) <= 3:
        raise ContractError("selection_ref_count")
    identities = [canonical(ref) for ref in refs]
    if len(set(identities)) != len(identities):
        raise ContractError("selection_duplicate_ref")
    permitted = {canonical(ref) for ref in selected_refs}
    for ref in refs:
        if canonical(ref) not in permitted:
            raise ContractError("selection_invisible_ref")
        _selected(snapshot, ref)
    note = nonempty(decision["context_for_action"], "context_for_action")
    if len(note) > 1200:
        raise ContractError("selection_note_over_limit")
    return decision


def render_reminder(decision: dict, *, snapshot: dict, cycle_id: str,
                    commit_id: str, reviewed_refs: list[dict]) -> dict:
    if decision["decision"] != "remind":
        raise ContractError("not_a_reminder")
    reviewed = {canonical(ref) for ref in reviewed_refs}
    anchors = []
    for ref in decision["refs"]:
        item, content, component = _selected(snapshot, ref)
        if ref["type"] == "state":
            origin = (item["claim"]["assertion_origin"] if item["kind"] ==
                      "knowledge" else item["episode"]["result"]["assertion_origin"])
            temporal = (item["claim"]["time_role"] if item["kind"] ==
                        "knowledge" else "past_episode")
            status = item["use_status"]
            scope = item["scope"]
            mode = ("uncertain_claim" if status == "contested" else
                    "historical_record" if status == "historical_only" or
                    temporal == "past_episode" else
                    "conditional_experience" if item["kind"] == "procedural" else
                    "current_claim")
        elif ref["type"] == "requirement":
            origin, temporal, status, scope, mode = (
                "model_interpretation_of_user_requirement", "task_version_bound",
                item["status"], None, "requirement")
        else:
            origin, temporal, status, scope, mode = (
                "model_gap", "task_version_bound", item["status"], None, "gap")
        anchors.append({"ref": ref, "component": component, "render_mode": mode,
            "origin_badge": origin, "temporal_badge": temporal,
            "use_status": status,
            "gap_kind": item["gap_kind"] if ref["type"] == "gap" else None,
            "uncertainty_badge": "contested" if status == "contested" else None,
            "content": content, "scope": scope,
            "reviewed_this_cycle": canonical(ref) in reviewed,
            "committed_event_seq": snapshot["committed_event_seq"]})
        if ref["type"] == "state" and item["kind"] == "procedural" and item["lesson"]:
            anchors.append({"ref": ref, "component": "lesson",
                "render_mode": "uncertain_claim" if status == "contested" else
                               "historical_record" if status == "historical_only" else
                               "conditional_experience",
                "origin_badge": "inference", "temporal_badge": "general_hypothesis",
                "use_status": status, "gap_kind": None,
                "uncertainty_badge": "contested" if status == "contested" else None,
                "content": item["lesson"]["text"], "scope": scope,
                "reviewed_this_cycle": canonical(ref) in reviewed,
                "committed_event_seq": snapshot["committed_event_seq"]})
    reminder_id = "reminder-" + digest([snapshot["episode_id"], cycle_id,
                                        commit_id])[:24]
    rendered = {"state_version": snapshot["state_version"],
        "task_version": snapshot["B"]["G"]["task_version"],
        "phase2_view_id": decision["phase2_view_id"],
        "reminder_id": reminder_id, "anchors": anchors,
        "generated_note": {"role": "advisory_interpretation",
                           "text": decision["context_for_action"]}}
    if len(canonical(rendered)) > 16384:
        raise ContractError("reminder_rendered_over_limit")
    return rendered


def attach_once(*, store, reminder: dict, task_messages: list[dict],
                request_id: str, cycle_id: str,
                send: Callable[[list[dict]], object]) -> object:
    """The label is an auxiliary user turn, not a replacement user command."""
    if store.delivery_result(reminder["reminder_id"]) is not None:
        raise ContractError("reminder_already_delivered")
    if any(row["phase"] == "delivery_attempt" and row["body"].get(
            "reminder_id") == reminder["reminder_id"] for row in
            store.journal_rows(cycle_id)):
        raise ContractError("delivery_outcome_unknown_check_journal")
    if store.delivery_attempt_cycles(reminder["reminder_id"]):
        raise ContractError("delivery_outcome_unknown_check_journal")
    snapshot = store.snapshot()
    if (snapshot["state_version"] != reminder["state_version"] or
            store.goals()["epoch"] != reminder["task_version"]):
        raise ContractError("selection_stale")
    messages = deepcopy(task_messages)
    messages.append({"role": "user", "content":
        "Auxiliary memory information; not a new user requirement.\n" +
        canonical(reminder).decode("utf-8")})
    store.journal(cycle_id, "delivery_attempt", {"reminder_id": reminder["reminder_id"],
        "request_id": request_id, "messages_sha256": digest(messages)})
    response = send(messages)
    if type(response) is not dict or response.get("accepted") is not True:
        raise ContractError("task_response_not_accepted")
    store.delivery(reminder["reminder_id"], request_id,
                   {"status": "included_in_accepted_request",
                    "request_id": request_id, "messages_sha256": digest(messages)})
    return response
