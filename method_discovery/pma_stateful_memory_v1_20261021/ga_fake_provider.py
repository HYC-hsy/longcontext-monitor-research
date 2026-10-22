"""Finite, explicitly scripted offline responses for the GA bridge.

The script names response *shapes*, not binding IDs or evidence IDs. Those
are read from the actual request. No network client is imported here.
"""

from __future__ import annotations

import json
from pathlib import Path

from .source import ContractError, canonical


ROLES = frozenset({"maintenance", "audit", "candidate_repair",
                   "audit_correction", "selection"})
SHAPES = frozenset({"empty", "observed_state", "clean", "silent", "remind"})


class FiniteGAFakeProvider:
    def __init__(self, script: list[dict]):
        if not isinstance(script, list) or not script:
            raise ContractError("fake_script_missing")
        self.script = []
        for row in script:
            if (type(row) is not dict or
                    set(row) not in ({"role", "shape"}, {"role", "shape", "envelope"}) or
                    row["role"] not in ROLES or row["shape"] not in SHAPES):
                raise ContractError("fake_script_invalid")
            if row.get("envelope", "raw_json") not in {"raw_json", "fenced_json"}:
                raise ContractError("fake_script_invalid")
            self.script.append(dict(row))
        self.calls = []

    @classmethod
    def from_file(cls, path: str | Path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def __call__(self, role, messages, call_id, max_output):
        if not self.script:
            raise ContractError("fake_script_exhausted")
        row = self.script.pop(0)
        if row["role"] != role:
            raise ContractError("fake_role_mismatch")
        payload = json.loads(messages[1]["content"])
        shape = row["shape"]
        self.calls.append({"role": role, "call_id": call_id, "shape": shape})
        if role in {"maintenance", "candidate_repair"}:
            if shape not in {"empty", "observed_state"}:
                raise ContractError("fake_shape_mismatch")
            binding = payload["binding"]
            patch = {"entity_upserts": [], "state_upserts": [],
                     "relation_upserts": [], "record_transitions": []}
            if shape == "observed_state":
                observed = next((source for source in payload["source_catalog"]
                    if source["purpose"] == "maintenance" and
                    source["source_kind"] == "tool_result" and
                    source["text"]), None)
                if observed is None:
                    raise ContractError("fake_observation_missing")
                quote = observed["text"]
                patch["entity_upserts"] = [{"entity_id": "@workspace",
                    "entity_type": "environment", "display_name": "synthetic workspace"}]
                patch["state_upserts"] = [{"record_id": "@observed", "revision": 1,
                    "entity_id": "@workspace", "scope": {"task_id": binding["task_id"],
                    "entity_ids": ["@workspace"], "conditions": []},
                    "use_status": "active", "updated_at_step": 1, "supersedes": [],
                    "kind": "knowledge", "claim": {"text": quote,
                    "assertion_origin": "tool_observation", "time_role": "present_fact",
                    "support_refs": [{"evidence_id": observed["evidence_id"],
                                      "quote": quote}], "challenge_refs": []}}]
            answer = {"protocol": "maintenance-proposal/1",
                "request_id": binding["request_id"],
                "active_task_version": binding["active_task_version"],
                "base_state_version": binding["base_state_version"],
                "world_patch": patch, "specification_upserts": [],
                "gap_upserts": [], "gap_resolutions": [], "gap_reopens": [],
                "focus": {"op": "keep"}}
        elif role in {"audit", "audit_correction"}:
            if shape != "clean":
                raise ContractError("fake_shape_mismatch")
            answer = {"protocol": "audit-result/2", "binding": payload["binding"],
                "outcome": "clean",
                "issues": [], "closure_assessments": [], "unusable_reason": None}
        else:
            if shape not in {"silent", "remind"}:
                raise ContractError("fake_shape_mismatch")
            binding = payload["binding"]
            answer = {"decision": shape, "state_version": binding["state_version"],
                "task_version": binding["task_version"],
                "phase2_view_id": binding["phase2_view_id"]}
            if shape == "remind":
                state = next((ref for ref in payload["selected_refs"] if
                              ref["type"] == "state"), None)
                if state is None:
                    raise ContractError("fake_reminder_ref_missing")
                answer.update(refs=[state], context_for_action=
                              "If useful, review this observed tool result.")
        raw = canonical(answer).decode("utf-8")
        return "```json\n" + raw + "\n```" if row.get("envelope") == "fenced_json" else raw
