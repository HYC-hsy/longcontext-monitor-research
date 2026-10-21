"""Pinned PMA BM25 ranking plus deterministic, whole-bundle working sets."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import __future__
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .source import ContractError, digest


_BM25_PATH = (Path(__file__).resolve().parents[1] /
    "curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/"
    "vendor/pma_89e5c0d/src/memory_agent/memory/bm25_search.py")
_BM25_SHA256 = "9d4169c482e3aeef11ace9d6d87dbadc015b0a1ac2d4c1906b4b0f901bbe376b"


def _pinned_bm25():
    source = _BM25_PATH.read_bytes()
    # Windows worktrees may be CRLF while the fixed Git blob is LF.
    if hashlib.sha256(source.replace(b"\r\n", b"\n")).hexdigest() != _BM25_SHA256:
        raise ContractError("pma_bm25_source_mismatch")
    name = "_stateful_memory_pinned_pma_bm25"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, _BM25_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        if sys.version_info < (3, 10):
            # The pinned file uses PEP 604 annotations; postpone only their
            # evaluation on an older offline Python. Its algorithm is unchanged.
            code = compile(source.decode("utf-8"), str(_BM25_PATH), "exec",
                           flags=__future__.annotations.compiler_flag,
                           dont_inherit=True)
            exec(code, module.__dict__)
        else:
            spec.loader.exec_module(module)
    return module


def record_text(record: dict) -> str:
    if record["kind"] == "knowledge":
        return record["claim"]["text"]
    episode = record["episode"]
    return "\n".join([episode["conditions"]["text"], episode["action_text"],
                      episode["result"]["text"],
                      record["lesson"]["text"] if record["lesson"] else ""])


def query_text(task: str, supplements: list[str], steps: list[dict],
               recent_steps: int = 8, commands_per_step: int = 5) -> str:
    parts = [task, *supplements]
    for step in steps[-recent_steps:]:
        commands = step.get("commands", [])
        parts.extend(str(command) for command in commands[:commands_per_step])
        if len(commands) > commands_per_step:
            parts.append(f"[{len(commands) - commands_per_step} commands omitted]")
        if step.get("observation") is not None:
            parts.append(str(step["observation"]))
    return "\n".join(parts)


class MemoryIndex:
    def __init__(self, snapshot: dict) -> None:
        self.state_version = snapshot["state_version"]
        self.state_hash = digest(snapshot)
        self.records = [record for record in snapshot["B"]["W"]["states"]
                        if record["use_status"] != "retracted"]
        self.by_kind = {kind: [record for record in self.records
                               if record["kind"] == kind]
                        for kind in ("knowledge", "procedural")}
        self.bm25 = _pinned_bm25()
        self.indices = {kind: self.bm25.BM25Index([record_text(item)
                        for item in items], self.bm25.BM25Params(k1=1.5, b=0.75))
                        for kind, items in self.by_kind.items()}

    def select(self, query: str, *, threshold: int = 50,
               top_k: int = 20) -> list[dict]:
        if len(self.records) <= threshold:
            return list(self.records)
        ranked = {kind: [self.by_kind[kind][index] for index in
                          self.indices[kind].search(query, top_k=top_k)]
                  for kind in ("knowledge", "procedural")}
        selected = []
        for rank in range(top_k):
            for kind in ("knowledge", "procedural"):
                if rank < len(ranked[kind]):
                    selected.append(ranked[kind][rank])
        return selected


def _record_source_refs(record: dict) -> list[dict]:
    claims = ([record["claim"]] if record["kind"] == "knowledge" else
              [record["episode"]["conditions"], record["episode"]["result"],
               record["lesson"]] if record["lesson"] else
              [record["episode"]["conditions"], record["episode"]["result"]])
    refs = [ref for claim in claims for key in ("support_refs", "challenge_refs")
            for ref in claim[key]]
    if record["kind"] == "procedural":
        refs += record["episode"]["action_refs"]
    return refs


def _complete_bundle(record: dict, world: dict, ledger: dict,
                     linked_gaps: list[dict], archive: dict | None = None,
                     context_chars: int = 80) -> dict:
    archive = archive or {}
    entity_ids = {record["entity_id"]}
    entity_ids.update(record.get("scope", {}).get("entity_ids", []))
    current = {item["record_id"]: item for item in world["states"]}
    linked_versions = []
    seen_versions = {(record["record_id"], record["revision"])}
    for gap in linked_gaps:
        direct_refs = list(gap["record_refs"])
        if gap["closure"] and gap["closure"]["kind"] == "environment_supported":
            direct_refs += gap["closure"]["state_refs"]
        for ref in direct_refs:
            identity = (ref["record_id"], ref["revision"])
            if identity in seen_versions:
                continue
            seen_versions.add(identity)
            item = current.get(identity[0])
            if item is None or item["revision"] != identity[1]:
                item = archive.get(identity)
            if item is None:
                raise ContractError("source_unavailable", str(identity))
            linked_versions.append(item)
            entity_ids.add(item["entity_id"])
            entity_ids.update(item.get("scope", {}).get("entity_ids", []))
    relations = [relation for relation in world["relations"]
                 if relation["anchored_by"]["record_id"] == record["record_id"]]
    for relation in relations:
        entity_ids.update((relation["from_entity_id"], relation["to_entity_id"]))
    source_refs = list(_record_source_refs(record))
    for linked in linked_versions:
        source_refs.extend(_record_source_refs(linked))
    for gap in linked_gaps:
        if gap["closure"] and gap["closure"]["kind"] == "environment_supported":
            source_refs.extend(gap["closure"]["evidence_refs"])
    by_source = {}
    for ref in source_refs:
        by_source.setdefault(ref["source_id"], []).append(ref)
    sources = []
    for source_id in sorted(by_source):
        leaf = ledger[source_id]
        intervals = sorted((max(0, ref["start"] - context_chars),
                            min(len(leaf["text"]), ref["end"] + context_chars))
                           for ref in by_source[source_id])
        merged = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        sources.append({"source_id": source_id, "event_id": leaf["event_id"],
            "source_kind": leaf["source_kind"], "truncated": leaf["truncated"],
            "text_sha256": leaf["text_sha256"],
            "visible_spans": [{"start": start, "end": end,
                               "text": leaf["text"][start:end]}
                              for start, end in merged],
            "exact_refs": by_source[source_id]})
        if leaf["source_kind"] == "tool_result":
            actions = [item for item in ledger.values()
                       if item["event_id"] == leaf["event_id"] and
                       item["source_kind"] == "executed_action"]
            if not actions:
                sources[-1]["source_context_status"] = "source_context_unavailable"
            else:
                sources[-1]["executed_actions"] = actions
    return {"state": record,
            "linked_state_versions": linked_versions,
            "entities": [item for item in world["entities"]
                         if item["entity_id"] in entity_ids],
            "relations": relations, "linked_closed_gaps": linked_gaps,
            "sources": sources}


def visible_stored_source_refs(work: dict) -> list[dict]:
    """Typed stored refs in this frozen workset, never a recursive JSON search."""
    refs = []
    def requirement(item):
        refs.extend(item["source_refs"])
        retirement = item["retirement"]
        if retirement and retirement["kind"] == "interpretation_replaced":
            refs.extend(retirement["source_refs"])
    def state(item):
        claims = ([item["claim"]] if item["kind"] == "knowledge" else
                  [item["episode"]["conditions"], item["episode"]["result"]] +
                  ([item["lesson"]] if item["lesson"] is not None else []))
        for claim in claims:
            refs.extend(claim["support_refs"])
            refs.extend(claim["challenge_refs"])
        if item["kind"] == "procedural":
            refs.extend(item["episode"]["action_refs"])
    def gap(item):
        closure = item["closure"]
        if closure and closure["kind"] == "environment_supported":
            refs.extend(closure["evidence_refs"])
    for item in work["mandatory"]["G"]["specifications"]:
        requirement(item)
    for item in work["mandatory"]["open_gaps"]:
        gap(item)
    for item in work["mandatory"].get("historical_requirements", []):
        requirement(item)
    for bundle in [*work["mandatory"]["bundles"], *work["optional_bundles"]]:
        for item in [bundle["state"], *bundle.get("linked_state_versions", [])]:
            state(item)
        for item in bundle.get("linked_closed_gaps", []):
            gap(item)
        for item in bundle.get("historical_requirements", []):
            requirement(item)
    return refs


@dataclass
class Workset:
    mandatory: dict
    observation_batch: dict
    optional_bundles: list[dict]
    omissions: list[dict]
    source_window_id: str

    def payload(self) -> dict:
        return {"mandatory": self.mandatory,
                "observation_batch": self.observation_batch,
                "optional_bundles": self.optional_bundles,
                "omissions": self.omissions,
                "source_window_id": self.source_window_id}


class WorksetBuilder:
    def __init__(self, *, input_limit: int = 32768) -> None:
        self.input_limit = input_limit

    def build(self, snapshot: dict, events: list[dict], ledger: dict,
              ranked: list[dict], cycle_id: str, frozen_tip: int,
              measure: Callable[[dict], int],
              archive: dict[tuple[str, int], dict] | None = None,
              previous_attempt_diagnostics: list[dict] | None = None) -> Workset:
        archive = archive or {}
        world = snapshot["B"]["W"]
        gaps = snapshot["B"]["DeltaE"] + snapshot["B"]["DeltaA"]
        open_gaps = [gap for gap in gaps if gap["status"] in {"open", "blocked"}]
        required_refs = [ref for gap in open_gaps for ref in gap["record_refs"]]
        required_ids = {ref["record_id"] for ref in required_refs}
        if snapshot["B"]["F"]:
            required_ids.update(ref["record_id"] for gap in open_gaps
                if gap["gap_id"] == snapshot["B"]["F"]["gap_ref"]["gap_id"]
                for ref in gap["record_refs"])
        mandatory_bundles = []
        def linked_closed(record_id: str) -> list[dict]:
            return [gap for gap in gaps if gap["status"] not in {"open", "blocked"}
                    and (any(ref["record_id"] == record_id for ref in
                             gap["record_refs"]) or
                         gap["closure"] and gap["closure"]["kind"] ==
                         "environment_supported" and any(ref["record_id"] ==
                             record_id for ref in gap["closure"]["state_refs"]))]
        for record in world["states"]:
            if record["record_id"] in required_ids:
                mandatory_bundles.append(_complete_bundle(record, world, ledger,
                    linked_closed(record["record_id"]), archive))
        head_revisions = {item["record_id"]: item["revision"] for item in
                          world["states"]}
        for ref in required_refs:
            identity = (ref["record_id"], ref["revision"])
            if ref["record_id"] not in head_revisions:
                raise ContractError("missing_current_head", ref["record_id"])
            if head_revisions.get(ref["record_id"]) != ref["revision"]:
                historical = archive.get(identity)
                if historical is None:
                    raise ContractError("source_unavailable", str(identity))
                if not any(bundle["state"]["record_id"] == identity[0] and
                           bundle["state"]["revision"] == identity[1] for bundle in
                           mandatory_bundles):
                    bundle = _complete_bundle(historical, world, ledger, [], archive)
                    bundle["historical_revision"] = True
                    mandatory_bundles.append(bundle)
        mandatory = {"G": snapshot["B"]["G"], "open_gaps": open_gaps,
                     "F": snapshot["B"]["F"], "bundles": mandatory_bundles}
        current_requirements = {item["requirement_id"]: item for item in
                                snapshot["B"]["G"]["specifications"]}
        historical_requirements = []
        seen_requirements = set()
        def historical_for(linked_gaps):
            found = []
            for gap in linked_gaps:
                for ref in gap["goal_refs"]:
                    head = current_requirements.get(ref["requirement_id"])
                    if head and (head["revision"], head["task_version"]) == (
                            ref["revision"], ref["task_version"]):
                        continue
                    identity = ("requirement", ref["requirement_id"], ref["revision"])
                    old = archive.get(identity)
                    if old is None or old["task_version"] != ref["task_version"]:
                        raise ContractError("source_unavailable", str(identity))
                    found.append(old)
            return found
        for bundle in mandatory_bundles:
            for old in historical_for(bundle["linked_closed_gaps"]):
                identity = ("requirement", old["requirement_id"], old["revision"])
                if identity not in seen_requirements:
                    historical_requirements.append(old)
                    seen_requirements.add(identity)
        mandatory["historical_requirements"] = historical_requirements
        batch = {"cycle_id": cycle_id,
                 "base_committed_event_seq": snapshot["committed_event_seq"],
                 "frozen_tip_event_seq": frozen_tip,
                 "processing_range": {"from_event_seq": snapshot[
                     "committed_event_seq"] + 1,
                     "to_event_seq": snapshot["committed_event_seq"]},
                 "events": [], "previous_attempt_diagnostics":
                     previous_attempt_diagnostics or [],
                 "pending_after_batch_count": len(events)}
        work = Workset(mandatory, batch, [], [],
                       digest([cycle_id, snapshot["state_version"], frozen_tip]))
        if measure(work.payload()) > self.input_limit:
            raise ContractError("input_budget_exceeded", "mandatory")
        for event in events:
            expected = batch["processing_range"]["to_event_seq"] + 1
            if event["event_seq"] != expected:
                raise ContractError("noncontiguous_pending")
            entry = {"event_id": event["event_id"], "event_seq": event["event_seq"],
                     "kind": event["kind"],
                     "occurred_at_step": event["occurred_at_step"],
                     "source_ids": event["source_ids"],
                     "delivery_kind": event.get("delivery_kind", "new"),
                     "previous_attempt_ids": event.get("previous_attempt_ids", []),
                     "source_leaves": [ledger[source_id] for source_id in
                                       event["source_ids"]]}
            batch["events"].append(entry)
            batch["processing_range"]["to_event_seq"] = event["event_seq"]
            batch["pending_after_batch_count"] -= 1
            if measure(work.payload()) > self.input_limit:
                batch["events"].pop()
                batch["processing_range"]["to_event_seq"] -= 1
                batch["pending_after_batch_count"] += 1
                if not batch["events"]:
                    raise ContractError("input_budget_exceeded", "earliest_atomic_event")
                break
        included = {bundle["state"]["record_id"] for bundle in mandatory_bundles}
        for record in ranked:
            if record["record_id"] in included:
                continue
            bundle = _complete_bundle(record, world, ledger,
                                      linked_closed(record["record_id"]), archive)
            bundle["historical_requirements"] = historical_for(
                bundle["linked_closed_gaps"])
            work.optional_bundles.append(bundle)
            if measure(work.payload()) > self.input_limit:
                work.optional_bundles.pop()
                omission = {"record_id": record["record_id"],
                            "reason": "optional_bundle_overflow"}
                work.omissions.append(omission)
                if measure(work.payload()) > self.input_limit:
                    raise ContractError("input_budget_exceeded", "omission_manifest")
            else:
                included.add(record["record_id"])
        return work
