"""Opt-in file handshake for a human decision at the completion boundary."""
from __future__ import annotations

import json
import os
import time
import threading
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from research_runtime import CompletionDecision, emit


class ManualInterventionInbox:
    """Run-scoped external input, independent of model/tool progress.

    Publish UTF-8 *.txt files by atomic rename into inbox/. Files are claimed
    into archive/ before delivery, never retried automatically after failure.
    Receipts mean interruption requested, not model uptake or successful repair.
    """

    def __init__(self, root, interrupt, *, poll_seconds=0.1):
        self.root = Path(root)
        self.inbox = self.root / "inbox"
        self.archive = self.root / "archive"
        self.interrupt = interrupt
        self.poll_seconds = poll_seconds
        self.stop = threading.Event()
        self.thread = None

    def _receipt(self, name, status, **details):
        with (self.root / "receipts.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": time.time(), "file": name,
                                     "status": status, **details}, ensure_ascii=False) + "\n")

    def start(self):
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.archive.mkdir(parents=True, exist_ok=True)
        # A reused run directory must not deliver a previous task's messages.
        if any(self.inbox.iterdir()) or any(self.archive.iterdir()):
            raise ValueError("Manual intervention directory must be fresh for this task")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self

    def _run(self):
        while not self.stop.is_set():
            try:
                self.poll_once()
            except Exception as exc:
                # Make transport failure visible; never turn it into silence.
                self._receipt("", "transport_failed", error=repr(exc))
                return
            self.stop.wait(self.poll_seconds)

    def poll_once(self):
        for path in sorted(self.inbox.glob("*.txt")):
            if self.stop.is_set():
                return
            claimed = self.archive / path.name
            if claimed.exists():
                self._receipt(path.name, "duplicate_filename")
                raise ValueError("Use a new filename for each intervention")
            path.rename(claimed)
            try:
                message = claimed.read_text(encoding="utf-8").strip()
                if not message:
                    raise ValueError("Empty intervention")
                request = self.interrupt(message)
                if is_dataclass(request):
                    request = asdict(request)
                self._receipt(path.name, "interruption_requested", request=request)
            except Exception as exc:
                self._receipt(path.name, "delivery_failed", error=repr(exc))

    def close(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
            if self.thread.is_alive():
                self._receipt("", "shutdown_pending")


class ManualCompletionBoundary:
    """Publish a proposal, then wait for an explicit human decision file.

    This mechanism is disabled unless ``GA_MANUAL_COMPLETION_DIR`` is set. It
    exposes only the public completion proposal and does not consult a checker.
    """

    def __init__(self, root: str, *, timeout_seconds: float = 300,
                 poll_seconds: float = 0.25) -> None:
        self.root = Path(root)
        self.timeout_seconds = float(timeout_seconds)
        self.poll_seconds = float(poll_seconds)
        self.root.mkdir(parents=True, exist_ok=True)

    def __call__(self, proposal: Any, turn: int,
                 provider_link: Mapping[str, Any] | None = None) -> CompletionDecision:
        proposal_path = self.root / f"proposal_{proposal.proposal_id}.json"
        decision_path = self.root / f"decision_{proposal.proposal_id}.json"
        payload = {
            "schema_version": "manual-completion-boundary/1",
            "proposal": proposal.as_payload(),
            "internal_turn": int(turn),
            "provider_link": dict(provider_link or {}),
        }
        temporary = proposal_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, proposal_path)
        emit("manual_completion_wait_started", {
            "proposal_id": proposal.proposal_id,
            "proposal_ref": str(proposal_path),
            "timeout_seconds": self.timeout_seconds,
        }, internal_turn=turn)

        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            if decision_path.exists():
                raw = json.loads(decision_path.read_text(encoding="utf-8"))
                decision_path.unlink()
                decision_name = raw["decision"]
                next_prompt = raw.get("next_prompt") or raw.get("message")
                if isinstance(next_prompt, str):
                    next_prompt = next_prompt.strip() or None
                if decision_name == "CONTINUE" and not next_prompt:
                    decision_name = "ABSTAIN"
                    reason_codes = ("MANUAL_CONTINUE_PROMPT_MISSING",)
                else:
                    reason_codes = tuple(
                        raw.get("reason_codes") or ("MANUAL_DECISION",)
                    )
                decision = CompletionDecision(
                    decision=decision_name,
                    reason_codes=reason_codes,
                    next_prompt=next_prompt,
                    target_obligation_ids=tuple(raw.get("target_obligation_ids") or ()),
                    checker_ids=(),
                )
                emit("manual_completion_wait_finished", {
                    "proposal_id": proposal.proposal_id,
                    "outcome": "decision_received",
                    "decision": decision.decision,
                }, internal_turn=turn)
                return decision
            time.sleep(self.poll_seconds)

        emit("manual_completion_wait_finished", {
            "proposal_id": proposal.proposal_id,
            "outcome": "timeout",
        }, internal_turn=turn)
        return CompletionDecision(
            decision="ABSTAIN", reason_codes=("MANUAL_DECISION_TIMEOUT",)
        )
