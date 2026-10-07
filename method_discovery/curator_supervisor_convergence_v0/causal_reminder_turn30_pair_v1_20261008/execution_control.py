"""Offline-testable causal-pair ordering and post-termination evaluator barrier.

No provider, Task Agent, or evaluator implementation is imported here.
Future live adapters must be bound by a separate explicit authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
import json
from pathlib import Path
import shutil
import tempfile
from typing import Callable, Optional


ORDER = ("control", "treatment")
LEGAL_TERMINAL_REASONS = frozenset({"normal_completion", "runner_termination", "task_turn_300"})


class PassiveCapture:
    """Append-only raw capture; never injects its records into a model input."""

    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            raise RuntimeError("Raw capture path already exists; refusing overwrite")
        path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, kind: str, payload: object) -> None:
        snapshot = copy.deepcopy(payload)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"kind": kind, "payload": snapshot}, ensure_ascii=False) + "\n")


@dataclass(frozen=True)
class ArmResult:
    arm: str
    terminal_reason: str
    termination_turn: int
    accepted_task_responses: int
    workspace_path: str
    raw_artifact_root: str
    infrastructure_error: Optional[str] = None


class PairController:
    def __init__(self):
        self._started = False
        self.events: list[dict] = []

    def run(self, execute_arm: Callable[[str], ArmResult],
            evaluate_workspace: Callable[[str], object]) -> dict:
        if self._started:
            raise RuntimeError("Pair controller is single-use; selective rerun forbidden")
        self._started = True
        results: list[ArmResult] = []
        for arm in ORDER:
            self.events.append({"event": "arm_started", "arm": arm})
            try:
                result = execute_arm(arm)
            except Exception as exc:
                self.events.append({"event": "infrastructure_failure", "arm": arm,
                                    "error_type": type(exc).__name__})
                return {"status": "infrastructure_invalid", "completed_arms": [r.arm for r in results],
                        "native_evaluator_executed": False, "events": list(self.events)}
            if (result.arm != arm or result.accepted_task_responses < 0
                    or result.accepted_task_responses > 270 or result.termination_turn < 30):
                raise RuntimeError("Arm adapter returned inconsistent mechanical identity")
            self.events.append({"event": "arm_terminated", "arm": arm,
                                "reason": result.terminal_reason,
                                "termination_turn": result.termination_turn,
                                "accepted_task_responses": result.accepted_task_responses,
                                "raw_artifact_root": result.raw_artifact_root})
            results.append(result)
            if (result.infrastructure_error or result.terminal_reason not in LEGAL_TERMINAL_REASONS
                    or result.termination_turn > 300):
                self.events.append({"event": "pair_invalidated", "arm": arm,
                                    "before_first_accepted_response": result.accepted_task_responses == 0})
                return {"status": "infrastructure_invalid", "completed_arms": [r.arm for r in results],
                        "native_evaluator_executed": False, "events": list(self.events)}
        # Both continuations are over before the first evaluator call.
        self.events.append({"event": "both_continuations_terminated"})
        evaluations = {}
        for result in results:
            self.events.append({"event": "native_evaluator_started_post_both", "arm": result.arm})
            try:
                # The native adapter sees a neutral /app copy, never the arm
                # directory name or the research artifacts beside that dir.
                with tempfile.TemporaryDirectory(prefix="causal_native_input_") as temporary:
                    neutral_app = Path(temporary) / "app"
                    shutil.copytree(result.workspace_path, neutral_app)
                    evaluations[result.arm] = evaluate_workspace(str(neutral_app))
            except Exception as exc:
                self.events.append({"event": "native_evaluator_failure", "arm": result.arm,
                                    "error_type": type(exc).__name__})
                return {"status": "evaluator_invalid", "completed_arms": list(ORDER),
                        "native_evaluator_executed": True, "events": list(self.events)}
        return {"status": "continuations_complete", "completed_arms": list(ORDER),
                "native_evaluator_executed": True, "evaluations": evaluations,
                "events": list(self.events)}
