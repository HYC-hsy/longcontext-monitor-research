"""Atomic first-completion checkpoint wiring for Stage 6D paired branches."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from checkpoint_runtime import create_r1_checkpoint
from research_runtime import emit


class FirstCompletionCheckpoint:
    """Capture exactly one pre-decision R1 checkpoint for a live Agent run."""

    def __init__(self, *, checkpoint_root: str, workspace_getter, client: Any,
                 identity: Mapping[str, Any], method_getter=None,
                 budget_getter=None) -> None:
        self.checkpoint_root = Path(checkpoint_root)
        self.workspace_getter = workspace_getter
        self.client = client
        self.identity = dict(identity)
        self.method_getter = method_getter or (lambda: None)
        self.budget_getter = budget_getter or (lambda: None)
        self.checkpoint_path: Path | None = None

    def __call__(self, proposal: Any, turn: int,
                 provider_link: Mapping[str, Any] | None = None) -> Path:
        if self.checkpoint_path is not None:
            return self.checkpoint_path
        workspace = self.workspace_getter()
        if not workspace:
            raise RuntimeError("Completion checkpoint requires an authoritative workspace")
        identity = dict(self.identity)
        identity["internal_turn"] = int(turn)
        if provider_link:
            identity["llm_call_id"] = provider_link.get("llm_call_id")
        method_state = self.method_getter()
        self.checkpoint_path = create_r1_checkpoint(
            checkpoint_root=self.checkpoint_root,
            workspace=workspace,
            client=self.client,
            identity=identity,
            boundary="pre_completion_decision",
            continuation={"completion_proposal": proposal.as_payload()},
            method_state=method_state,
            budget=self.budget_getter(),
        )
        emit("completion_checkpoint_frozen", {
            "checkpoint_id": self.checkpoint_path.name,
            "packet_ref": str(self.checkpoint_path / "packet.json"),
            "proposal_id": proposal.proposal_id,
            "internal_turn": int(turn),
        }, internal_turn=turn)
        return self.checkpoint_path


def checkpoint_identity_from_environment() -> dict[str, Any]:
    return {
        "experiment_id": os.environ.get("GA_EXPERIMENT_ID", "interactive"),
        "task_id": os.environ.get("GA_BENCH_TASK_ID", "interactive"),
        "run_id": os.environ.get("GA_BENCH_RUN_ID", "run"),
        "branch_id": os.environ.get("GA_BRANCH_ID", "original"),
        "user_turn": 0,
    }
