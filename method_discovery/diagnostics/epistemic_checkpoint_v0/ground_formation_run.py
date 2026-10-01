"""Run three one-shot Supervisor-only seed reviews, then capture idle checkpoints.

This is an explicit research entry point.  It does not start a Task Agent,
apply a transition, run a verifier, or judge whether a ground is sound.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .checkpoint import _tree_manifest
from .ground_formation_fixture import (
    archive_input, audit_model_input, capture_seed, create_workspace,
    sha256_bytes, summarize_audit,
)


RESEARCH_INPUT_MARKERS = (
    "case-a-control", "case-b-control", "case-c-control",
    "related-transition seed", "unrelated-transition seed",
    "measurement-boundary seed", "ground-formation fixture",
    "expected carry", "expected reopen", "future patch", "checkpoint id",
)


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")


def _rows(path: Path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _profile(path: Path, name: str):
    profile = _json(path)[name]
    if not all(profile.get(key) for key in ("apikey", "apibase", "model")):
        raise ValueError("existing model profile is incomplete")
    effective = dict(profile, monitor_dcec=True, monitor_semantic_continuity=True,
                     monitor_dcec_working_chars=4000, monitor_live_intervention=True)
    redacted = {key: value for key, value in effective.items()
                if key.lower() not in {"apikey", "api_key", "secret", "password"}}
    return effective, redacted


def _usage(root: Path):
    rows = _rows(root / "monitor_private" / "audit" / "provider_usage.jsonl")
    return {"records": len(rows), "raw": rows}


def _run_one(*, kind: str, run_id: str, live_root: Path, archive_root: Path,
             source_sha: str, profile_name: str, profile_path: Path,
             max_wait_seconds: int):
    # Live paths deliberately have no research case labels: Monitor review
    # exposes the absolute workspace/private paths in its environment map.
    work = live_root / "workspace"
    task = create_workspace(kind, work)
    effective, redacted = _profile(profile_path, profile_name)
    config = {"source_commit": source_sha, "model_profile": profile_name,
              "model_config": redacted, "max_review_turns": 20,
              "task_id": "synthetic:dispatcher-v0" if kind != "c" else "synthetic:view-v0",
              "run_timeout_seconds": max_wait_seconds,
              "independent_probe_total_requests": 0}
    identity = archive_input(archive_root, task, work, config)
    from monitor_agent_core.runtime import MonitorRuntime
    from monitor_agent_core.agent import DCEC_CONTINUATION_PROMPT

    mailbox = archive_root / "host_mailbox.jsonl"

    def receive_intervention(message):
        with mailbox.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"status": "queued_no_task_agent", "message": message},
                                    ensure_ascii=False) + "\n")
        return "queued_no_task_agent"

    monitor_root = live_root / "session"
    started = time.monotonic()
    runtime = MonitorRuntime(
        public_task=task, task_workspace=work, artifact_dir=monitor_root,
        config_name=profile_name, model_config=effective,
        interrupt_callback=receive_intervention, max_review_turns=20,
        task_id=config["task_id"], run_id=run_id,
        task_original_path=str(monitor_root / "task_evidence" / "original_task.txt"),
        run_timeout_seconds=max_wait_seconds,
        independent_probe_total_requests=0,
    )
    end_status = "unknown"
    try:
        deadline = time.monotonic() + max_wait_seconds
        while time.monotonic() < deadline:
            receipts = _rows(monitor_root / "runtime_receipts.jsonl")
            if any(row.get("kind") == "failure" for row in receipts):
                end_status = "runtime_failure"
                break
            if any(row.get("kind") == "ready" for row in receipts):
                end_status = "review_idle"
                break
            if not runtime._process.is_alive():
                end_status = "worker_exited_before_ready"
                break
            time.sleep(0.5)
        else:
            end_status = "review_timeout"
    finally:
        runtime.close()

    # Runtime is now stopped; no provider/tool work or Task-side writer exists.
    shutil.copytree(monitor_root, archive_root / "monitor")
    dialogue = archive_root / "monitor" / "monitor_private" / "audit" / "dialogue.jsonl"
    working = archive_root / "monitor" / "monitor_private" / "working.md"
    progress = _rows(archive_root / "monitor" / "monitor_private" / "audit" / "progress.jsonl")
    reviews = _rows(archive_root / "monitor" / "monitor_private" / "audit" / "reviews.jsonl")
    receipt_rows = _rows(archive_root / "monitor" / "runtime_receipts.jsonl")
    facts = summarize_audit(dialogue, working) if dialogue.is_file() else {}
    contamination = audit_model_input(dialogue, RESEARCH_INPUT_MARKERS) if dialogue.is_file() else {
        "checked": 0, "hits": [], "contaminated": None}
    _write(archive_root / "contamination_audit.json", contamination)
    review_finished = end_status == "review_idle" and len(reviews) == 1
    observed = facts.get("observed_task_tool", False)
    captured = None
    capture_error = None
    if review_finished and working.is_file() and observed and not contamination["contaminated"]:
        context = next((row for row in _rows(dialogue) if row.get("event") == "review_context"), None)
        review_started = next((row for row in progress if row.get("event") == "review_started"), None)
        if context and review_started:
            history = _json(archive_root / "monitor" / "monitor_private" / "audit" / "provider_history.json")
            system = context["system_prompt"]
            tools = context["tools"]
            identities = {
                "task_identity": identity["task_sha256"],
                "source_identity": source_sha,
                "system_prompt_sha256": sha256_bytes(system.encode("utf-8")),
                "continuation_prompt_sha256": sha256_bytes(DCEC_CONTINUATION_PROMPT.encode("utf-8")),
                "tool_schema_sha256": sha256_bytes(json.dumps(tools, sort_keys=True,
                    ensure_ascii=False).encode("utf-8")),
                "model_config_sha256": sha256_bytes(json.dumps(redacted, sort_keys=True,
                    ensure_ascii=False).encode("utf-8")),
            }
            boundary = {"review_id": review_started["review_id"],
                        "request_id": "initialization-" + review_started["review_id"],
                        "public_cursor": 0, "task_turn": 0,
                        "completion_control_state": {
                            "pending_completion": False,
                            "last_review_action": reviews[0].get("action"),
                            "host_mailbox_count": len(_rows(mailbox)),
                        }}
            probe_state = dict(boundary, task_writes_paused=True, supervisor_idle=True,
                               inflight_requests=0, inflight_tools=0)
            try:
                captured = capture_seed(
                    checkpoint_root=archive_root / "checkpoints",
                    checkpoint_id="seed-" + run_id,
                    workspace_root=work, working_path=working,
                    history_prefix=history, identities=identities,
                    boundary=boundary, boundary_probe=lambda: dict(probe_state),
                    review_finished=review_finished, observed_task_tool=observed,
                )
            except Exception as exc:
                capture_error = {"type": type(exc).__name__, "reason": str(exc)}
    _write(archive_root / "run_facts.json", {
        "run_id": run_id, "source_commit": source_sha, "task_sha256": identity["task_sha256"],
        "workspace_manifest_sha256": identity["workspace_manifest_sha256"],
        "end_status": end_status, "review_count": len(reviews),
        "model": redacted.get("model"), "profile": profile_name,
        "supervisor": facts, "usage": _usage(archive_root / "monitor"),
        "duration_seconds": time.monotonic() - started,
        "checkpoint": str(captured) if captured else None,
        "checkpoint_verify": "complete" if captured else "not_ready",
        "capture_error": capture_error,
        "contamination": contamination,
        "receipts": receipt_rows,
    })
    return end_status, captured


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", required=True, type=Path)
    parser.add_argument("--live-root", required=True, type=Path)
    parser.add_argument("--profile-file", required=True, type=Path)
    parser.add_argument("--profile", default="claude_monitor_opus48")
    parser.add_argument("--max-wait-seconds", type=int, default=1200)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo / "GenericAgent-main"))
    source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    if args.archive_root.exists():
        raise ValueError("archive root exists: refusing to overwrite")
    args.archive_root.mkdir(parents=True)
    for kind, run_id, label in (("a", "gff-v0-20261002-01", "case_a"),
                                ("b", "gff-v0-20261002-02", "case_b"),
                                ("c", "gff-v0-20261002-03", "case_c")):
        live = args.live_root / f"s0{ord(kind)-ord('a')+1}"
        if live.exists():
            raise ValueError("live directory exists: refusing to reuse")
        live.mkdir(parents=True)
        archive = args.archive_root / label
        print(json.dumps({"event": "starting", "run_id": run_id}), flush=True)
        status, captured = _run_one(
            kind=kind, run_id=run_id, live_root=live, archive_root=archive,
            source_sha=source_sha, profile_name=args.profile,
            profile_path=args.profile_file, max_wait_seconds=args.max_wait_seconds,
        )
        print(json.dumps({"event": "finished", "run_id": run_id, "status": status,
                          "checkpoint": str(captured) if captured else None}), flush=True)
        if status != "review_idle":
            break  # infrastructure stop; preserve the scene and unstarted cases.


if __name__ == "__main__":
    main()
