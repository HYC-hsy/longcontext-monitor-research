"""Synchronous, fake-safe stateful memory cycle; no built-in network transport."""

from __future__ import annotations

from typing import Callable

from .audit import AuditCodec, _diff, validate_audit_result
from .budget import TokenProxy
from .prompts import audit, maintenance, repair, selection
from .proposal import build_candidate, validate_proposal
from .projection import project_snapshot, visible_existing
from .reminder import render_reminder, validate_selection
from .retrieval import MemoryIndex, WorksetBuilder, query_text
from .source import ContractError, SourceCatalog, digest, strict_loads


def _operation_index(before: dict, candidate: dict, patch: dict) -> list[dict]:
    paths = (("entity_upserts", "W", "entities", "entity_id", "entity"),
             ("state_upserts", "W", "states", "record_id", "state"),
             ("relation_upserts", "W", "relations", "relation_id", "relation"),
             ("record_transitions", "W", "states", "record_id", "state"),
             ("specification_upserts", "G", "specifications", "requirement_id",
              "requirement"),
             ("gap_upserts", "B", None, "gap_id", "gap"),
             ("gap_resolutions", "B", None, "gap_id", "gap"),
             ("gap_reopens", "B", None, "gap_id", "gap"))
    entries = []
    for operation, parent, name, id_field, kind in paths:
        items = patch["world_patch"][operation] if operation in patch[
            "world_patch"] else patch[operation]
        def collection(snapshot):
            belief = snapshot["B"]
            return (belief["DeltaE"] + belief["DeltaA"] if name is None else
                    belief[parent][name])
        old = {item[id_field]: item for item in collection(before)}
        new = {item[id_field]: item for item in collection(candidate)}
        for item in items:
            identifier = (item["record_ref"]["record_id"] if operation ==
                          "record_transitions" else item[id_field])
            body = new[identifier]
            target = {"kind": kind, "id": identifier}
            if "revision" in body:
                target["revision"] = body["revision"]
            entries.append({"operation": operation, "target_ref": target,
                "changed_field_paths": _diff(old.get(identifier), body)})
    if patch["focus"]["op"] != "keep":
        entries.append({"operation": "focus_" + patch["focus"]["op"],
            "target_ref": {"kind": "focus", "id": "F"},
            "changed_field_paths": _diff(before["B"]["F"], candidate["B"]["F"])})
    return entries


class CycleEngine:
    """One host trigger advances at most one contiguous prefix and one selection.

    A provider is an explicitly supplied callable. It receives a role, immutable
    messages, a stable call ID and max output; no real-provider fallback exists.
    """

    def __init__(self, store, provider: Callable, *, task_text: str,
                 token_proxy: TokenProxy | None = None) -> None:
        self.store = store
        self.provider = provider
        self.task_text = task_text
        self.proxy = token_proxy or TokenProxy()

    def _call(self, cycle_id: str, role: str, messages: list[dict],
              number: int, max_output: int) -> str:
        count = self.proxy.enforce(messages)
        call_id = f"{cycle_id}/{number}/{role}"
        self.store.journal(cycle_id, "call_prepared", {"call_id": call_id,
            "role": role, "messages_sha256": digest(messages),
            "input_size": count, "max_output_tokens": max_output})
        # Write-ahead attempt: an exception after the provider accepts a request
        # is unknown, never a reason to send it again in this or a new cycle.
        self.store.journal(cycle_id, "call_attempt", {"call_id": call_id})
        raw = self.provider(role, messages, call_id, max_output)
        if type(raw) is not str:
            raise ContractError("provider_nontext_response")
        self.store.journal(cycle_id, "call_returned", {"call_id": call_id,
            "public_response_sha256": digest(raw), "characters": len(raw)})
        return raw

    def _catalog(self, ledger: dict, work: dict,
                 purposes: tuple[str, ...] = ("maintenance", "audit")) -> tuple[SourceCatalog, list[dict]]:
        catalog = SourceCatalog(ledger, work["source_window_id"])
        visible = []
        seen = set()
        def add(source_id: str, start: int, end: int,
                exact_stored_ref: bool = False) -> None:
            if start == end:
                return
            for purpose in purposes:
                identity = (source_id, start, end, purpose, exact_stored_ref)
                if identity in seen:
                    continue
                seen.add(identity)
                span = catalog.add(source_id, start, end, purpose,
                                   exact_stored_ref=exact_stored_ref)
                visible.append({"evidence_id": span.evidence_id,
                    "source_id": source_id, "source_kind": ledger[source_id]["source_kind"],
                    "event_seq": ledger[source_id]["event_seq"],
                    "start": start, "end": end, "purpose": purpose,
                    "exact_stored_ref": exact_stored_ref,
                    "text": ledger[source_id]["text"][start:end]})
        for entry in work["observation_batch"]["events"]:
            for leaf in entry["source_leaves"]:
                add(leaf["source_id"], 0, len(leaf["text"]))
        for bundle in [*work["mandatory"]["bundles"],
                       *work["optional_bundles"]]:
            for source in bundle["sources"]:
                for span in source["visible_spans"]:
                    add(source["source_id"], span["start"], span["end"])
                for ref in source["exact_refs"]:
                    add(source["source_id"], ref["start"], ref["end"], True)
        for ref in work["mandatory"]["G"]["original_user_sources"]:
            add(ref["source_id"], ref["start"], ref["end"])
        return catalog, visible

    def run(self, trigger_id: str) -> dict:
        if not trigger_id:
            raise ContractError("missing_trigger_id")
        snapshot = self.store.snapshot()
        if snapshot is None:
            raise ContractError("uninitialized_episode")
        cycle_id = "cycle-" + digest([snapshot["episode_id"], trigger_id])[:24]
        prior = self.store.journal_rows(cycle_id)
        if prior:
            terminal = [row["body"] for row in prior if row["phase"] == "cycle_result"]
            if terminal:
                return terminal[-1]
            # Re-entry cannot reset the shared repair credit or repeat an
            # accepted/unknown call. A future real trigger may replay pending.
            raise ContractError("cycle_outcome_unknown_check_journal", cycle_id)
        frozen_tip = max((event["event_seq"] for event in
                          self.store.events_after(0)), default=0)
        goals = self.store.goals()
        pending = [event for event in self.store.events_after(
                   snapshot["committed_event_seq"]) if event["event_seq"] <= frozen_tip]
        if not pending and snapshot["state_version"] > 0:
            result = {"cycle_id": cycle_id, "status": "no_pending",
                      "logical_calls": 0}
            self.store.journal(cycle_id, "cycle_result", result)
            return result
        self.store.journal(cycle_id, "cycle_started", {"base_hash": digest(snapshot),
            "tip": frozen_tip, "goal_epoch": goals["epoch"],
            "pending_event_ids": [event["event_id"] for event in pending]})
        calls = 0
        credit = 1
        stage = "preparation"
        try:
            ledger = self.store.sources()
            prior_attempts = self.store.failed_attempts_for({event["event_id"]
                for event in pending})
            pending = [{**event, "delivery_kind": "replayed",
                "previous_attempt_ids": [attempt["attempt_id"] for attempt in
                    prior_attempts if event["event_id"] in attempt["event_ids"]]}
                if any(event["event_id"] in attempt["event_ids"] for attempt in
                       prior_attempts) else event for event in pending]
            index = MemoryIndex(snapshot)
            if index.state_hash != digest(snapshot):
                raise ContractError("index_unavailable")
            recent = self.store.events_after(max(0, frozen_tip - 8))
            query = query_text(self.task_text,
                [ledger[source_id]["text"] for source_id in goals["messages"][1:]],
                [event["payload"] for event in recent])
            ranked = index.select(query)
            def prepare_maintenance(body):
                catalog, visible = self._catalog(ledger, body)
                before_view = project_snapshot(snapshot, snapshot, body)
                binding = {"cycle_id": cycle_id,
                    "request_id": f"{cycle_id}/maintenance",
                    "task_id": snapshot["task_id"],
                    "episode_id": snapshot["episode_id"],
                    "active_task_version": goals["epoch"],
                    "base_state_version": snapshot["state_version"],
                    "base_state_hash": digest(snapshot),
                    "source_window_id": body["source_window_id"]}
                payload = {"protocol": "maintenance-input/1", "binding": binding,
                    "before_view": before_view,
                    "observation_batch": body["observation_batch"],
                    "working_set": {"mandatory": body["mandatory"],
                                    "optional_bundles": body["optional_bundles"],
                                    "omissions": body["omissions"]},
                    "source_catalog": visible,
                    "mutation_scope": {"visible_existing_refs": sorted(
                        [{"kind": kind, "id": identifier} for kind, identifier in
                         visible_existing(snapshot, body)],
                        key=lambda item: (item["kind"], item["id"])),
                        "new_local_ids_allowed": True}}
                binding["maintenance_view_id"] = digest(payload)
                return payload, catalog, visible
            def measure(body):
                payload, _catalog, _visible = prepare_maintenance(body)
                return self.proxy.measure(maintenance(payload))["proxy_tokens"]
            work = WorksetBuilder().build(snapshot, pending, ledger, ranked,
                                          cycle_id, frozen_tip, measure,
                                          archive=self.store.archive(),
                                          previous_attempt_diagnostics=prior_attempts)
            body = work.payload()
            self.store.journal(cycle_id, "workset_frozen", {"event_ids": [item[
                "event_id"] for item in body["observation_batch"]["events"]],
                "source_window_id": work.source_window_id,
                "workset_hash": digest(body)})
            maintenance_input, catalog, visible = prepare_maintenance(body)
            before_view = maintenance_input["before_view"]
            mutable_ids = visible_existing(snapshot, body)
            binding = maintenance_input["binding"]
            messages = maintenance(maintenance_input)
            proposal = None
            candidate = None
            while candidate is None:
                calls += 1
                stage = "provider"
                raw = self._call(cycle_id, "maintenance", messages, calls, 8192)
                stage = "model_validation"
                try:
                    response = strict_loads(raw)
                    proposal = validate_proposal(response,
                        request_id=binding["request_id"], task_version=goals["epoch"],
                        base_version=snapshot["state_version"])
                    candidate = build_candidate(proposal=proposal, base=snapshot,
                        catalog=catalog, cycle_id=cycle_id,
                        processed_to=body["observation_batch"]["processing_range"][
                            "to_event_seq"], goal_ledger=goals,
                        visible_existing_ids=mutable_ids, archive=self.store.archive())
                except ContractError as error:
                    if credit == 0:
                        raise
                    credit = 0
                    self.store.journal(cycle_id, "repair_credit_used",
                        {"mode": "maintenance_contract", "error_code": error.code})
                    messages = repair(original_messages=messages, base=before_view,
                        rejected=raw, raw_response=raw, error=error.code,
                        mode="maintenance_contract")
            while True:
                resolving = candidate["canonical_patch"]["gap_resolutions"]
                manifest = [{"resolution_id": item["gap_id"],
                             "gap_before": next((gap for gap in snapshot["B"][
                                "DeltaE"] + snapshot["B"]["DeltaA"] if
                                gap["gap_id"] == item["gap_id"]), None),
                             "gap_after": next((gap for gap in candidate["candidate"][
                                 "B"]["DeltaE"] + candidate["candidate"]["B"]["DeltaA"]
                                 if gap["gap_id"] == item["gap_id"]), None),
                             "closure_kind": item["closure"]["kind"] if
                                 item["closure"] else None} for item in resolving]
                audit_binding = {"cycle_id": cycle_id,
                    "task_version": goals["epoch"],
                    "base_state_hash": digest(snapshot),
                    "candidate_state_hash": digest(candidate["candidate"]),
                    "source_window_id": work.source_window_id}
                after_view = project_snapshot(candidate["candidate"], snapshot, body)
                audit_binding["before_view_hash"] = digest(before_view)
                audit_binding["candidate_view_hash"] = digest(after_view)
                current_revisions = {item["record_id"]: item["revision"] for item in
                    snapshot["B"]["W"]["states"]}
                contextual = []
                seen_history = set()
                for bundle in [*body["mandatory"]["bundles"],
                               *body["optional_bundles"]]:
                    for historical in [bundle["state"],
                                       *bundle.get("linked_state_versions", [])]:
                        identity = (historical["record_id"], historical["revision"])
                        if (current_revisions.get(identity[0]) != identity[1] and
                                identity not in seen_history):
                            contextual.append({"kind": "archived_state",
                                "record_ref": {"type": "state", "record_id": identity[0],
                                               "revision": identity[1]},
                                "body": historical})
                            seen_history.add(identity)
                view = AuditCodec().encode(before_view, after_view,
                    binding=audit_binding, sources=[v for v in visible if
                        v["purpose"] == "audit"],
                    observations=body["observation_batch"],
                    operation_index=_operation_index(before_view, after_view,
                                                     candidate["canonical_patch"]),
                    resolve_manifest=manifest,
                    contextual_objects=contextual)
                audit_messages = audit(view)
                calls += 1
                stage = "provider"
                raw = self._call(cycle_id, "audit", audit_messages, calls, 8192)
                stage = "model_validation"
                try:
                    response = strict_loads(raw)
                    result = validate_audit_result(response, view=view,
                        catalog=catalog, archive={("state", item["record_ref"][
                            "record_id"], item["record_ref"]["revision"]): item["body"]
                            for item in contextual})
                except ContractError as error:
                    if credit == 0:
                        raise
                    credit = 0
                    self.store.journal(cycle_id, "repair_credit_used",
                        {"mode": "audit_contract", "error_code": error.code})
                    correction = repair(original_messages=audit_messages,
                        base=before_view, rejected=after_view,
                        raw_response=raw, error=error.code, mode="audit_contract")
                    calls += 1
                    stage = "provider"
                    corrected_raw = self._call(cycle_id, "audit_correction",
                                               correction, calls, 8192)
                    stage = "model_validation"
                    result = validate_audit_result(strict_loads(corrected_raw), view=view,
                        catalog=catalog, archive={("state", item["record_ref"][
                            "record_id"], item["record_ref"]["revision"]): item["body"]
                            for item in contextual})
                if result["outcome"] == "unusable":
                    raise ContractError("model_unusable")
                if result["outcome"] == "clean":
                    break
                if credit == 0:
                    raise ContractError("blocking_issues_repair_exhausted")
                credit = 0
                self.store.journal(cycle_id, "repair_credit_used",
                    {"mode": "candidate_semantic", "issue_ids": [issue["issue_id"]
                        for issue in result["issues"]]})
                repair_messages = repair(original_messages=messages, base=before_view,
                    rejected={"candidate": after_view,
                              "proposal": proposal, "issues": result["issues"]},
                    raw_response=raw, error="blocking_issues", mode="replacement_proposal")
                calls += 1
                stage = "provider"
                replacement_raw = self._call(cycle_id, "candidate_repair",
                                             repair_messages, calls, 8192)
                stage = "model_validation"
                proposal = validate_proposal(strict_loads(replacement_raw),
                    request_id=binding["request_id"], task_version=goals["epoch"],
                    base_version=snapshot["state_version"])
                candidate = build_candidate(proposal=proposal, base=snapshot,
                    catalog=catalog, cycle_id=cycle_id,
                    processed_to=body["observation_batch"]["processing_range"][
                        "to_event_seq"], goal_ledger=goals,
                    visible_existing_ids=mutable_ids, archive=self.store.archive())
            stage = "commit"
            committed = self.store.compare_and_swap(update_id=candidate["update_id"],
                cycle_id=cycle_id, base=snapshot, candidate=candidate["candidate"],
                archive_delta=candidate["archive_delta"])
            self.store.journal(cycle_id, "committed", committed)
            if candidate["candidate"]["committed_event_seq"] != frozen_tip:
                outcome = {"cycle_id": cycle_id, "status": "committed_backlog_pending",
                    "commit": committed, "logical_calls": calls,
                    "pending_after_batch_count": body["observation_batch"][
                        "pending_after_batch_count"]}
            else:
                outcome = self._select(cycle_id, candidate["candidate"],
                    committed, body, view["required_coverage"], calls)
            self.store.journal(cycle_id, "cycle_result", outcome)
            return outcome
        except BaseException as error:
            category = error.code if isinstance(error, ContractError) else type(error).__name__
            status = ("init_failed" if snapshot["state_version"] == 0 and
                      not pending else
                      "update_rejected" if category == "blocking_issues_repair_exhausted" else
                      "update_unusable" if stage == "model_validation" and
                      isinstance(error, ContractError) else "runtime_failed")
            failure = {"cycle_id": cycle_id, "status": status, "error_code": category,
                       "failure_stage": stage,
                       "logical_calls": calls, "frontier": self.store.snapshot()[
                           "committed_event_seq"]}
            self.store.journal(cycle_id, "cycle_result", failure)
            return failure

    def _select(self, cycle_id: str, snapshot: dict, committed: dict,
                body: dict, reviewed_coverage: list[dict],
                calls: int) -> dict:
        try:
            if snapshot["B"]["G"]["task_version"] != self.store.goals()["epoch"]:
                raise ContractError("selection_stale")
            current_index = MemoryIndex(snapshot)
            if current_index.state_hash != digest(snapshot):
                raise ContractError("index_unavailable")
            ledger = self.store.sources()
            query = query_text(self.task_text,
                [ledger[source_id]["text"] for source_id in self.store.goals()[
                    "messages"][1:]], [event["payload"] for event in
                               self.store.events_after(max(0, snapshot[
                                   "committed_event_seq"] - 8))])
            selected = current_index.select(query)
            def refs_for(work):
                projected = project_snapshot(snapshot, snapshot, work)
                refs = [{"type": "state", "record_id": item["record_id"],
                         "revision": item["revision"]} for item in projected[
                             "B"]["W"]["states"] if item["use_status"] != "retracted"]
                refs += [{"type": "requirement", "requirement_id": item[
                    "requirement_id"], "revision": item["revision"],
                    "task_version": item["task_version"]} for item in projected[
                        "B"]["G"]["specifications"] if item["status"] == "active"]
                refs += [{"type": "gap", "gap_id": item["gap_id"],
                          "revision": item["revision"],
                          "task_version": item["task_version"]} for item in
                         projected["B"]["DeltaE"] + projected["B"]["DeltaA"] if
                         item["status"] in {"open", "blocked"}]
                return refs, projected
            def prepare_selection(work):
                refs, projected = refs_for(work)
                _catalog, visible = self._catalog(ledger, work, ("selection",))
                coverage = {(item["kind"], item["id"], item.get("revision")) for
                            item in reviewed_coverage}
                reviewed = [ref for ref in refs if (ref["type"], ref.get(
                    "record_id", ref.get("requirement_id", ref.get("gap_id"))),
                    ref.get("revision")) in coverage]
                not_reviewed = [ref for ref in refs if ref not in reviewed]
                view_id = digest([cycle_id, committed["candidate_hash"], refs])
                return {"binding": {"cycle_id": cycle_id,
                    "state_version": snapshot["state_version"],
                    "task_version": snapshot["B"]["G"]["task_version"],
                    "phase2_view_id": view_id}, "committed_view": projected,
                    "recent_activity": body["observation_batch"],
                    "source_catalog": visible, "selected_refs": refs,
                    "reviewed_this_cycle_refs": reviewed,
                    "not_reviewed_this_cycle_refs": not_reviewed}
            def measure(work):
                return self.proxy.measure(selection(prepare_selection(work)))[
                    "proxy_tokens"]
            selection_work = WorksetBuilder().build(snapshot, [], ledger, selected,
                cycle_id + "/selection", snapshot["committed_event_seq"], measure,
                archive=self.store.archive()).payload()
            select_input = prepare_selection(selection_work)
            refs = select_input["selected_refs"]
            phase2_view_id = select_input["binding"]["phase2_view_id"]
            answer_raw = self._call(cycle_id, "selection", selection(select_input),
                                    calls + 1, 2048)
            decision = validate_selection(strict_loads(answer_raw), snapshot=snapshot,
                phase2_view_id=phase2_view_id, selected_refs=refs)
            if decision["decision"] == "silent":
                return {"cycle_id": cycle_id, "status": "committed_selection_silent",
                        "commit": committed, "logical_calls": calls + 1}
            reminder = render_reminder(decision, snapshot=snapshot,
                cycle_id=cycle_id, commit_id=committed["update_id"],
                reviewed_refs=select_input["reviewed_this_cycle_refs"])
            return {"cycle_id": cycle_id, "status": "committed_reminder_ready",
                    "commit": committed, "reminder": reminder,
                    "logical_calls": calls + 1}
        except BaseException as error:
            code = error.code if isinstance(error, ContractError) else type(error).__name__
            status = ("committed_selection_stale" if code == "selection_stale" else
                      "committed_selection_failed")
            return {"cycle_id": cycle_id, "status": status,
                    "commit": committed, "error_code": code,
                    "logical_calls": calls + 1}
