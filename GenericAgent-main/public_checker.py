"""Workspace-bounded command checkers for evidence-gated method discovery."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from obligation_ledger import EVIDENCE_SCHEMA


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


class PublicCommandChecker:
    """Run frozen public checks without a shell or exposing their output to the Agent."""

    def __init__(self, specs: Sequence[Mapping[str, Any]],
                 workspace_resolver: Callable[[], str | os.PathLike[str] | None]):
        self.specs = {}
        self.workspace_resolver = workspace_resolver
        self.invocations = 0
        for raw in specs:
            spec = self._validate_spec(raw)
            if spec["checker_id"] in self.specs:
                raise ValueError(f"Duplicate checker_id: {spec['checker_id']}")
            self.specs[spec["checker_id"]] = spec

    @staticmethod
    def _validate_spec(raw: Mapping[str, Any]) -> dict[str, Any]:
        checker_id = str(raw.get("checker_id") or "").strip()
        argv = raw.get("argv")
        if not checker_id or not isinstance(argv, list) or not argv:
            raise ValueError("checker requires checker_id and non-empty argv")
        if any(not isinstance(item, str) or not item or "\x00" in item for item in argv):
            raise ValueError(f"Invalid argv for checker {checker_id}")
        cwd = str(raw.get("cwd", "."))
        if Path(cwd).is_absolute():
            raise ValueError(f"Checker cwd must be workspace-relative: {checker_id}")
        timeout_sec = float(raw.get("timeout_sec", 120))
        if timeout_sec <= 0 or timeout_sec > 1800:
            raise ValueError(f"Checker timeout out of bounds: {checker_id}")
        pass_exit_codes = raw.get("pass_exit_codes", [0])
        if not isinstance(pass_exit_codes, list) or any(not isinstance(x, int) for x in pass_exit_codes):
            raise ValueError(f"Invalid pass_exit_codes: {checker_id}")
        return {
            "checker_id": checker_id,
            "argv": tuple(argv),
            "cwd": cwd,
            "timeout_sec": timeout_sec,
            "pass_exit_codes": tuple(pass_exit_codes),
            "strength": str(raw.get("strength") or "LOCAL_BEHAVIOR_CHECK"),
        }

    def __call__(self, obligation, predicate) -> Mapping[str, Any]:
        spec = self.specs.get(predicate.checker_id)
        if spec is None:
            raise ValueError(f"No public checker spec for {predicate.checker_id}")
        workspace_raw = self.workspace_resolver()
        if not workspace_raw:
            raise RuntimeError("Task workspace is not ready for checking")
        workspace = Path(workspace_raw).resolve()
        cwd = (workspace / spec["cwd"]).resolve()
        try:
            cwd.relative_to(workspace)
        except ValueError as error:
            raise ValueError(f"Checker cwd escapes workspace: {predicate.checker_id}") from error
        if not cwd.is_dir():
            raise FileNotFoundError(f"Checker cwd does not exist: {cwd}")

        self.invocations += 1
        timed_out = False
        try:
            completed = subprocess.run(
                spec["argv"], cwd=cwd, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=spec["timeout_sec"], check=False,
            )
            returncode = completed.returncode
            stdout, stderr = completed.stdout, completed.stderr
            result = "pass" if returncode in spec["pass_exit_codes"] else "fail"
        except subprocess.TimeoutExpired as error:
            timed_out = True
            returncode = None
            stdout, stderr = error.stdout or b"", error.stderr or b""
            result = "error"

        checked_input = {
            "checker_id": predicate.checker_id,
            "argv": spec["argv"],
            "cwd": spec["cwd"],
            "subject_version": obligation.version,
            "returncode": returncode,
            "timed_out": timed_out,
            "stdout_sha256": _digest(stdout),
            "stderr_sha256": _digest(stderr),
        }
        content_hash = _digest(json.dumps(
            checked_input, sort_keys=True, separators=(",", ":")
        ).encode("utf-8"))
        return {
            "schema_version": EVIDENCE_SCHEMA,
            "evidence_id": f"{predicate.checker_id}-v{obligation.version}-n{self.invocations}",
            "obligation_id": obligation.obligation_id,
            "predicate_ids": [predicate.predicate_id],
            "checker_id": predicate.checker_id,
            "result": result,
            "strength": spec["strength"],
            "subject_version": obligation.version,
            "artifact_refs": [f"checker://{predicate.checker_id}/{content_hash}"],
            "content_hash": content_hash,
        }


def checker_from_card(card: Mapping[str, Any], workspace_resolver) -> PublicCommandChecker | None:
    specs = card.get("checker_specs", [])
    return PublicCommandChecker(specs, workspace_resolver) if specs else None
