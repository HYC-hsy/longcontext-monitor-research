"""Synchronous, fake-safe stateful memory cycle; no built-in network transport."""

from __future__ import annotations

from typing import Callable

from .audit import AuditCodec, validate_audit_result
from .budget import TokenProxy
from .prompts import audit, maintenance, repair, selection
from .proposal import build_candidate, validate_proposal
from .reminder import render_reminder, validate_selection
from .retrieval import MemoryIndex, WorksetBuilder, query_text
from .source import ContractError, SourceCatalog, digest, strict_loads


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

    def _catalog(self, ledger: dict, work: dict) -> tuple[SourceCatalog, list[dict]]:
        catalog = SourceCatalog(ledger, work["source_window_id"])
        visible = []
        seen = set()
        def add(source_id: str, start: int, end: int,
                exact_stored_ref: bool = False) -> None:
            if start == end:
                return
            for purpose in ("maintenance", "audit"):
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
        if not pending:
            result = {"cycle_id": cycle_id, "status": "no_pending",
                      "logical_calls": 0}
            self.store.journal(cycle_id, "cycle_result", result)
            return result
        self.store.journal(cycle_id, "cycle_started", {"base_hash": digest(snapshot),
            "tip": frozen_tip, "goal_epoch": goals["epoch"],
            "pending_event_ids": [event["event_id"] for event in pending]})
        calls = 0
        credit = 1
        try:
            ledger = self.store.sources()
            index = MemoryIndex(snapshot)
            if index.state_hash != digest(snapshot):
                raise ContractError("index_unavailable")
            recent = self.store.events_after(max(0, frozen_tip - 8))
            query = query_text(self.task_text, [], [event["payload"] for event in recent])
            ranked = index.select(query)
            def prepare_maintenance(body):
                catalog, visible = self._catalog(ledger, body)
                binding = {"cycle_id": cycle_id,
                    "request_id": f"{cycle_id}/maintenance",
                    "task_id": snapshot["task_id"],
                    "episode_id": snapshot["episode_id"],
                    "active_task_version": goals["epoch"],
                    "base_state_version": snapshot["state_version"],
                    "base_state_hash": digest(snapshot),
                    "source_window_id": body["source_window_id"]}
                payload = {"protocol": "maintenance-input/1", "binding": binding,
                    "before_view": snapshot,
                    "observation_batch": body["observation_batch"],
                    "working_set": {"mandatory": body["mandatory"],
                                    "optional_bundles": body["optional_bundles"],
                                    "omissions": body["omissions"]},
                    "source_catalog": visible,
                    "mutation_scope": {"visible_existing_refs": [r["record_id"] for r
                        in snapshot["B"]["W"]["states"]],
                        "new_local_ids_allowed": True}}
                binding["maintenance_view_id"] = digest(payload)
                return payload, catalog, visible
            def measure(body):
                payload, _catalog, _visible = prepare_maintenance(body)
                return self.proxy.measure(maintenance(payload))["proxy_tokens"]
            work = WorksetBuilder().build(snapshot, pending, ledger, ranked,
                                          cycle_id, frozen_tip, measure)
            body = work.payload()
            maintenance_input, catalog, visible = prepare_maintenance(body)
            binding = maintenance_input["binding"]
            messages = maintenance(maintenance_input)
            proposal = None
            candidate = None
            while candidate is None:
                calls += 1
                raw = self._call(cycle_id, "maintenance", messages, calls, 8192)
                try:
                    response = strict_loads(raw)
                    proposal = validate_proposal(response,
                        request_id=binding["request_id"], task_version=goals["epoch"],
                        base_version=snapshot["state_version"])
                    candidate = build_candidate(proposal=proposal, base=snapshot,
                        catalog=catalog, cycle_id=cycle_id,
                        processed_to=body["observation_batch"]["processing_range"][
                            "to_event_seq"], goal_ledger=goals,
                        visible_existing_ids={r["record_id"] for r in
                            snapshot["B"]["W"]["states"]}, archive=self.store.archive())
                except ContractError as error:
                    if credit == 0:
                        raise
                    credit = 0
                    self.store.journal(cycle_id, "repair_credit_used",
                        {"mode": "maintenance_contract", "error_code": error.code})
                    messages = repair(original_messages=messages, base=snapshot,
                        rejected=raw, raw_response=raw, error=error.code,
                        mode="maintenance_contract")
            while True:
                resolving = proposal["gap_resolutions"]
                manifest = [{"resolution_id": item["gap_id"],
                             "gap_before": next((gap for gap in snapshot["B"][
                                "DeltaE"] + snapshot["B"]["DeltaA"] if
                                gap["gap_id"] == item["gap_id"]), None),
                             "gap_after": item,
                             "closure_kind": item["closure"]["kind"] if
                                 item["closure"] else None} for item in resolving]
                audit_binding = {"cycle_id": cycle_id,
                    "task_version": goals["epoch"],
                    "base_state_hash": digest(snapshot),
                    "candidate_state_hash": digest(candidate["candidate"]),
                    "source_window_id": work.source_window_id}
                view = AuditCodec().encode(snapshot, candidate["candidate"],
                    binding=audit_binding, sources=[v for v in visible if
                        v["purpose"] == "audit"],
                    observations=body["observation_batch"],
                    operation_index=[{"op": name, "count": len(value)} for name,
                        value in proposal["world_patch"].items()],
                    resolve_manifest=manifest,
                    contextual_objects=[*body["mandatory"]["bundles"],
                                        *body["optional_bundles"]])
                audit_messages = audit(view)
                calls += 1
                raw = self._call(cycle_id, "audit", audit_messages, calls, 8192)
                try:
                    response = strict_loads(raw)
                    result = validate_audit_result(response, view=view,
                        catalog=catalog, archive={})
                except ContractError as error:
                    if credit == 0:
                        raise
                    credit = 0
                    self.store.journal(cycle_id, "repair_credit_used",
                        {"mode": "audit_contract", "error_code": error.code})
                    correction = repair(original_messages=audit_messages,
                        base=snapshot, rejected=candidate["candidate"],
                        raw_response=raw, error=error.code, mode="audit_contract")
                    calls += 1
                    corrected_raw = self._call(cycle_id, "audit_correction",
                                               correction, calls, 8192)
                    result = validate_audit_result(strict_loads(corrected_raw), view=view,
                        catalog=catalog, archive={})
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
                repair_messages = repair(original_messages=messages, base=snapshot,
                    rejected={"candidate": candidate["candidate"],
                              "proposal": proposal, "issues": result["issues"]},
                    raw_response=raw, error="blocking_issues", mode="replacement_proposal")
                calls += 1
                replacement_raw = self._call(cycle_id, "candidate_repair",
                                             repair_messages, calls, 8192)
                proposal = validate_proposal(strict_loads(replacement_raw),
                    request_id=binding["request_id"], task_version=goals["epoch"],
                    base_version=snapshot["state_version"])
                candidate = build_candidate(proposal=proposal, base=snapshot,
                    catalog=catalog, cycle_id=cycle_id,
                    processed_to=body["observation_batch"]["processing_range"][
                        "to_event_seq"], goal_ledger=goals,
                    visible_existing_ids={r["record_id"] for r in
                        snapshot["B"]["W"]["states"]}, archive=self.store.archive())
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
                    committed, body, visible, calls)
            self.store.journal(cycle_id, "cycle_result", outcome)
            return outcome
        except BaseException as error:
            category = error.code if isinstance(error, ContractError) else type(error).__name__
            failure = {"cycle_id": cycle_id, "status": "failed", "error_code": category,
                       "logical_calls": calls, "frontier": self.store.snapshot()[
                           "committed_event_seq"]}
            self.store.journal(cycle_id, "cycle_result", failure)
            return failure

    def _select(self, cycle_id: str, snapshot: dict, committed: dict,
                body: dict, visible: list[dict],
                calls: int) -> dict:
        try:
            if snapshot["B"]["G"]["task_version"] != self.store.goals()["epoch"]:
                raise ContractError("selection_stale")
            current_index = MemoryIndex(snapshot)
            if current_index.state_hash != digest(snapshot):
                raise ContractError("index_unavailable")
            query = query_text(self.task_text, [], [event["payload"] for event in
                               self.store.events_after(max(0, snapshot[
                                   "committed_event_seq"] - 8))])
            selected = current_index.select(query)
            refs = [{"type": "state", "record_id": item["record_id"],
                     "revision": item["revision"]} for item in selected]
            refs += [{"type": "requirement", "requirement_id": item["requirement_id"],
                      "revision": item["revision"], "task_version": item["task_version"]}
                     for item in snapshot["B"]["G"]["specifications"] if
                     item["status"] == "active"]
            refs += [{"type": "gap", "gap_id": item["gap_id"],
                      "revision": item["revision"], "task_version": item["task_version"]}
                     for item in snapshot["B"]["DeltaE"] + snapshot["B"]["DeltaA"]
                     if item["status"] in {"open", "blocked"}]
            phase2_view_id = digest([cycle_id, committed["candidate_hash"], refs])
            select_input = {"binding": {"cycle_id": cycle_id,
                "state_version": snapshot["state_version"],
                "task_version": snapshot["B"]["G"]["task_version"],
                "phase2_view_id": phase2_view_id},
                "committed_view": snapshot, "recent_activity": body[
                    "observation_batch"], "source_catalog": visible,
                "selected_refs": refs,
                "reviewed_this_cycle_refs": refs,
                "not_reviewed_this_cycle_refs": []}
            answer_raw = self._call(cycle_id, "selection", selection(select_input),
                                    calls + 1, 2048)
            decision = validate_selection(strict_loads(answer_raw), snapshot=snapshot,
                phase2_view_id=phase2_view_id, selected_refs=refs)
            if decision["decision"] == "silent":
                return {"cycle_id": cycle_id, "status": "committed_selection_silent",
                        "commit": committed, "logical_calls": calls + 1}
            reminder = render_reminder(decision, snapshot=snapshot,
                cycle_id=cycle_id, commit_id=committed["update_id"],
                reviewed_refs=refs)
            return {"cycle_id": cycle_id, "status": "committed_reminder_ready",
                    "commit": committed, "reminder": reminder,
                    "logical_calls": calls + 1}
        except BaseException as error:
            code = error.code if isinstance(error, ContractError) else type(error).__name__
            return {"cycle_id": cycle_id, "status": "committed_selection_failed",
                    "commit": committed, "error_code": code,
                    "logical_calls": calls + 1}
