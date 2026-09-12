"""Bounded priority-aware residual repair at completion boundaries."""
from __future__ import annotations

from typing import Any, Mapping

from research_runtime import CompletionDecision, emit


POLICIES = {
    "A0_ATOMIC": (False, False),
    "A1_PRIORITY": (True, False),
    "A2_RESIDUAL": (False, True),
    "A3_PRIORITY_RESIDUAL": (True, True),
}


class PriorityResidualRecoveryGate:
    """Keep public counterexamples atomic and re-open unresolved residuals once."""

    def __init__(self, atoms: list[Mapping[str, Any]], policy_id: str,
                 max_recovery_episodes: int = 2):
        if policy_id not in POLICIES:
            raise ValueError("unsupported priority-residual policy")
        if max_recovery_episodes != 2:
            raise ValueError("current experiment freezes exactly two recovery episodes")
        ids = [str(atom.get("atom_id", "")) for atom in atoms]
        if not ids or any(not item for item in ids) or len(ids) != len(set(ids)):
            raise ValueError("atoms need unique non-empty IDs")
        self.policy_id = policy_id
        self.priority_enabled, self.residual_enabled = POLICIES[policy_id]
        self.max_recovery_episodes = max_recovery_episodes
        self.atoms = {str(atom["atom_id"]): dict(atom) for atom in atoms}
        self.status = {atom_id: "open" for atom_id in ids}
        self.events: list[dict[str, Any]] = []
        self._processed_event_count = 0
        self._armed = False
        self._episodes = 0
        self._history: list[dict[str, Any]] = []

    def record_turn(self, tool_calls: list[Mapping[str, Any]],
                    tool_results: list[Mapping[str, Any]], turn: int) -> None:
        results = {str(item.get("tool_use_id", "")): item.get("content", "")
                   for item in tool_results}
        for call in tool_calls:
            name = str(call.get("tool_name", ""))
            if name == "no_tool":
                continue
            self.events.append({
                "event_id": f"residual-tool-{len(self.events) + 1:05d}",
                "turn": turn, "tool_name": name, "arguments": call.get("args", {}),
                "content": str(results.get(str(call.get("id", "")), ""))[:12000],
            })

    @staticmethod
    def _priority(atom: Mapping[str, Any]) -> tuple[int, int, int, int, str]:
        order = {
            "hard": 0, "soft": 1, "optional": 2,
            "imminent": 0, "active": 1, "low": 2,
            "global": 0, "branch": 1, "edge_case": 2,
            "high": 0, "medium": 1, "low_confidence": 2,
        }
        return (
            order.get(str(atom.get("contract_force")), 9),
            order.get(str(atom.get("closure_risk")), 9),
            order.get(str(atom.get("impact_scope")), 9),
            order.get(str(atom.get("evidence_confidence")), 9),
            str(atom.get("atom_id")),
        )

    def _ordered_open(self) -> list[dict[str, Any]]:
        atoms = [self.atoms[item] for item, status in self.status.items() if status == "open"]
        return sorted(atoms, key=self._priority) if self.priority_enabled else atoms

    def _render(self, atoms: list[Mapping[str, Any]], residual: bool) -> str:
        heading = (
            "A previous repair changed only part of the public conflict. Revisit the remaining "
            "atomic residuals before finishing:"
            if residual else
            "Before finishing, inspect these independent public-contract discrepancies:"
        )
        lines = [heading]
        for rank, atom in enumerate(atoms, 1):
            label = str(atom.get("priority_label", "UNRANKED")) if self.priority_enabled else "UNRANKED"
            lines.extend([
                f"\n[Atomic discrepancy {rank} | {label}]",
                f"Requirement: {atom['requirement_quote']}",
                f"Public source: {atom['source_event_id']} at {atom['path']}",
                f"Counterexample slice: {atom['counterexample_slice']}",
                f"Mismatch: {atom['conflict']}",
            ])
        lines.extend([
            "", "Each item has its own closure state; fixing one does not close the others.",
            "These are monitor hypotheses, not checker verdicts. Inspect the cited public source, "
            "decide for yourself, revise if warranted, and continue the original task normally.",
        ])
        return "\n".join(lines)

    def _refresh_residuals(self) -> dict[str, Any]:
        before = dict(self.status)
        relevant = self.events[self._processed_event_count:]
        for event in relevant:
            if event["tool_name"] not in {"file_patch", "file_write"}:
                continue
            args = event.get("arguments", {})
            path = str(args.get("path", "")) if isinstance(args, Mapping) else ""
            new_content = str(args.get("new_content", args.get("content", "")))
            old_content = str(args.get("old_content", ""))
            for atom_id, atom in self.atoms.items():
                if self.status[atom_id] != "open" or path != str(atom["path"]):
                    continue
                needle = str(atom["counterexample_slice"])
                if needle in new_content:
                    continue
                if needle in old_content or event["tool_name"] == "file_write":
                    self.status[atom_id] = "resolved_by_public_change"
        self._processed_event_count = len(self.events)
        resolved = [item for item in self.status if before[item] == "open" and self.status[item] != "open"]
        return {"resolved": resolved, "open": [item for item, value in self.status.items() if value == "open"]}

    def arm(self, proposal: Any) -> CompletionDecision:
        if self._armed:
            raise RuntimeError("priority residual gate already armed")
        self._armed = True
        self._episodes = 1
        atoms = self._ordered_open()
        decision = CompletionDecision(
            decision="VERIFY", reason_codes=("ATOMIC_RECOVERY_EPISODE", self.policy_id),
            next_prompt=self._render(atoms, residual=False),
            target_obligation_ids=tuple(dict.fromkeys(str(item["obligation_id"]) for item in atoms)),
        )
        self._history.append({"episode": 1, "open": [item["atom_id"] for item in atoms]})
        emit("priority_residual_episode", {**self._history[-1], "policy_id": self.policy_id})
        return decision

    def decide(self, proposal: Any) -> CompletionDecision:
        if not self._armed:
            raise RuntimeError("priority residual gate was not armed")
        transition = self._refresh_residuals()
        open_atoms = self._ordered_open()
        if self.residual_enabled and open_atoms and self._episodes < self.max_recovery_episodes:
            self._episodes += 1
            row = {"episode": self._episodes, **transition,
                   "presented": [item["atom_id"] for item in open_atoms]}
            self._history.append(row)
            emit("priority_residual_episode", {**row, "policy_id": self.policy_id})
            return CompletionDecision(
                decision="VERIFY", reason_codes=("RESIDUAL_REPAIR_EPISODE", self.policy_id),
                next_prompt=self._render(open_atoms, residual=True),
                target_obligation_ids=tuple(dict.fromkeys(
                    str(item["obligation_id"]) for item in open_atoms
                )),
            )
        reason = "NO_OPEN_RESIDUAL" if not open_atoms else "BOUNDED_RECOVERY_COMPLETE"
        decision = CompletionDecision(
            decision="ALLOW_COMPLETE", reason_codes=(reason, self.policy_id),
        )
        emit("priority_residual_completion", {
            "policy_id": self.policy_id, "episodes": self._episodes, **transition,
        })
        return decision

    __call__ = decide

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": "priority-residual-gate/0", "policy_id": self.policy_id,
            "atoms": list(self.atoms.values()), "status": dict(self.status),
            "events": list(self.events), "processed_event_count": self._processed_event_count,
            "armed": self._armed, "episodes": self._episodes, "history": list(self._history),
        }

    def restore_snapshot(self, value: Mapping[str, Any]) -> None:
        if value.get("schema_version") == "priority-residual-gate/0":
            if value.get("policy_id") != self.policy_id:
                raise ValueError("priority residual policy mismatch")
            self.status = {str(k): str(v) for k, v in value.get("status", {}).items()}
            self.events = list(value.get("events", []))
            self._processed_event_count = int(value.get("processed_event_count", 0))
            self._armed = bool(value.get("armed", False))
            self._episodes = int(value.get("episodes", 0))
            self._history = list(value.get("history", []))

