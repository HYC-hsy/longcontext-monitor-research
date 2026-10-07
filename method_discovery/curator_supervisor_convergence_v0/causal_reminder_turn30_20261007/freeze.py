"""Freeze mechanical turn-30 checkpoint evidence; no inference or evaluator path."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
import subprocess

from .materialize import (ARCHIVE, CLEAN_GIT_HEAD, CLEAN_TAR, EXPECTED, HERE, IMAGE_APP,
                          IMAGE_APP_TREE_SHA256, ORIGINAL_TASK_SIDECAR, PUBLIC_EVENTS, REPO, RESEARCH_EVENTS,
                          RUNTIME_RECEIPTS, SOURCE_COMMIT, SOURCE_TAR, TASK, TASK_IMAGE,
                          jsonl, sha_bytes, sha_file, source_tree, verify_sources)
from .git_state import certify_git_state
from .runtime_checkpoint import DEPLOYED_SOURCE, certify as certify_runtime
from .reconstruct_next_request import (NEXT_ID, NEXT_SHA256, PREVIOUS_ID,
                                       PREVIOUS_SHA256, bound_first_send,
                                       canonical, comparison, request_path, sha)


MATERIALIZED = Path(r"E:\fyne_turn30_materialized_20261007_v4")
EXPECTED_WORKSPACE_TREE = "994ed5f372f0ee6fecda6a600dc970ce4c5fbbb1a8c09acfa9ab3748ce323c60"
DEPLOYED_TASK_AGENT_SOURCE = Path(r"E:\LongContext\long_context_bench\output\crs_rhr_rer_fyne_mechanism_gate\isolated_bundles\crs-rhr-rer-v0-fyne-bji-high-budget-r1\source\ga.py")
DEPLOYED_TASK_AGENT_SOURCE_SHA256 = "189c2272545b08dc61fd26a645df0ae0d0dbc07f0f62c8b713bb4f9a34bcb05a"


def write_json(name: str, value: object) -> None:
    (HERE / name).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _relative(path: Path) -> str:
    return path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)


def _line_hash(path: Path, number: int) -> str:
    return sha_bytes(path.read_bytes().splitlines(keepends=True)[number - 1])


def timeline() -> list[dict]:
    events = jsonl(PUBLIC_EVENTS)
    entries = []
    for sequence in (53, 54, 55, 56, 57, 58):
        row = next(event for event in events if event["archive_sequence"] == sequence)
        call = row["tool_calls"][0]
        entries.append({
            "archive_sequence": sequence, "task_turn": row["task_turn"],
            "event_type": row["boundary"], "actor_call_type": "Task Agent / " + call["name"],
            "model_visible_to_task_agent": True,
            "source_file": _relative(PUBLIC_EVENTS), "source_line": sequence,
            "content_sha256": _line_hash(PUBLIC_EVENTS, sequence),
            "description": ("assistant tool call" if row["boundary"] == "post_model_pre_tool"
                            else "tool result and next-prompt boundary"),
            "tool_call_id": call["id"], "tool_result_count": len(row["tool_results"]),
            "time_unix_seconds": row["archived_at"],
        })
    research = jsonl(RESEARCH_EVENTS)
    for line in (209, 210, 211, 212):
        row = research[line - 1]
        entries.append({
            "event_id": row["event_id"], "task_turn": 30 if line < 212 else 31,
            "event_type": row["event_type"], "actor_call_type": "Task Agent provider lifecycle",
            "model_visible_to_task_agent": False,
            "source_file": _relative(RESEARCH_EVENTS), "source_line": line,
            "content_sha256": _line_hash(RESEARCH_EVENTS, line),
            "description": "mechanical provider/history event; payload content is hash-only",
            "timestamp": row["timestamp"],
            "time_unix_seconds": datetime.fromisoformat(row["timestamp"]).timestamp(),
        })
    path, first_send = bound_first_send(NEXT_ID, NEXT_SHA256)
    entries.append({
        "event_id": NEXT_ID, "task_turn": 31, "event_type": "provider_request_pre_send",
        "actor_call_type": "Task Agent / Anthropic Messages",
        "model_visible_to_task_agent": True, "source_file": str(request_path(NEXT_ID)),
        "source_line": None, "content_sha256": NEXT_SHA256,
        "description": "exact raw request body, archive-hash-bound by first_send receipt",
        "archive_receipt_file": _relative(path),
        "archive_receipt_sha256": sha_file(path),
        "time_ns": first_send["time_ns"],
        "time_unix_seconds": first_send["time_ns"] / 1_000_000_000,
    })
    entries.sort(key=lambda item: item["time_unix_seconds"])
    return entries


def source_manifest() -> dict:
    inputs = []
    for path in (PUBLIC_EVENTS, RESEARCH_EVENTS, RUNTIME_RECEIPTS, TASK, SOURCE_TAR, CLEAN_TAR,
                 DEPLOYED_TASK_AGENT_SOURCE, DEPLOYED_SOURCE / "llmcore.py",
                 DEPLOYED_SOURCE / "agent_loop.py", DEPLOYED_SOURCE / "mykey.json",
                 request_path(PREVIOUS_ID), request_path(NEXT_ID)):
        inputs.append({"path": _relative(path), "bytes": path.stat().st_size,
                       "sha256": sha_file(path), "role": ("local_hash_bound_request_body"
                                                      if path.parent == request_path(PREVIOUS_ID).parent
                                                      else "source_or_clean_image_provenance")})
    for identifier, digest in ((PREVIOUS_ID, PREVIOUS_SHA256), (NEXT_ID, NEXT_SHA256)):
        path, _ = bound_first_send(identifier, digest)
        inputs.append({"path": _relative(path), "bytes": path.stat().st_size,
                       "sha256": sha_file(path), "role": "committed_bridge_request_hash_receipt"})
    for row in inputs:
        path = Path(row["path"])
        if not path.is_absolute():
            committed = subprocess.check_output(["git", "show", f"{SOURCE_COMMIT}:{row['path']}"], cwd=REPO)
            local = (REPO / path).read_bytes()
            if committed not in (local, local.replace(bytes([13, 10]), bytes([10]))):
                raise RuntimeError(f"Source commit mismatch: {row['path']}")
            row["source_commit_sha256"] = sha_bytes(committed)
            row["local_checkout_sha256"] = sha_bytes(local)
    return {"source_commit": SOURCE_COMMIT, "task_id": "fyn-2.2.0-roadmap",
            "clean_base_git_head": CLEAN_GIT_HEAD, "task_image": TASK_IMAGE,
            "clean_image_app_tree_sha256": IMAGE_APP_TREE_SHA256,
            "inputs": inputs}


def provider_history_manifest(messages: list[dict]) -> dict:
    items = []
    tool_uses = set()
    tool_results = set()
    for index, item in enumerate(messages):
        blocks = item["content"] if isinstance(item["content"], list) else []
        types = [block.get("type") for block in blocks]
        for block in blocks:
            if block.get("type") == "tool_use":
                tool_uses.add(block["id"])
            if block.get("type") == "tool_result":
                tool_results.add(block["tool_use_id"])
        items.append({"index": index, "role": item["role"], "content_types": types,
                      "content_sha256": sha(item["content"]),
                      "provider_specific_block_fields": sorted({key for block in blocks
                                                               for key in block if key in ("cache_control", "signature")})})
    if tool_uses != tool_results:
        raise RuntimeError("Provider history tool-call/result linkage incomplete")
    return {"model": "claude-opus-4-8", "provider": "anthropic", "api_mode": "messages",
            "history_item_count": len(messages), "history_canonical_bytes": len(canonical(messages)),
            "history_sha256": sha(messages), "tool_call_ids": sorted(tool_uses),
            "all_tool_calls_have_results": True, "items": items}


def freeze() -> dict:
    verify_sources()
    if sha_file(DEPLOYED_TASK_AGENT_SOURCE) != DEPLOYED_TASK_AGENT_SOURCE_SHA256:
        raise RuntimeError("Deployed Task Agent source identity mismatch")
    original, reconstructed, working, request_comparison = comparison()
    if not request_comparison["model_visible_equal"]:
        raise RuntimeError("Model-visible next-request reconstruction mismatch")
    workspace_tree, files = source_tree(MATERIALIZED, exclude_git=True)
    if workspace_tree != EXPECTED_WORKSPACE_TREE or len(files) != 2472:
        raise RuntimeError("Materialized turn-30 workspace identity mismatch")
    if sha_file(MATERIALIZED / ORIGINAL_TASK_SIDECAR) != EXPECTED[TASK]:
        raise RuntimeError("Historical original-task sidecar differs")
    if any(path.startswith(("monitor/", "verifier/", "solution/"))
           or (path.startswith(".monitor_original_task_") and path != ORIGINAL_TASK_SIDECAR)
           for path in (row["path"] for row in files)):
        raise RuntimeError("Private/future root entered checkpoint workspace")
    if any(row["path"] in ("IMPLEMENTATION_COMPLETE.md", "IMPLEMENTATION_SUMMARY.md") for row in files):
        raise RuntimeError("Future completion narrative entered checkpoint workspace")
    receipts = jsonl(RUNTIME_RECEIPTS)
    intervened_between = [row for row in receipts if row.get("kind") == "intervention"
                          and row.get("delivery_task_turn") == 30]
    selected = jsonl(RESEARCH_EVENTS)[208]
    if selected["event_type"] != "action_selected" or selected["payload"].get("intervention_event_id") is not None:
        raise RuntimeError("Turn-30 action-selection control boundary changed")
    if intervened_between:
        raise RuntimeError("Supervisor intervention delivered at the checkpoint boundary")
    git_state = certify_git_state(MATERIALIZED)
    runtime_state, runtime_request, runtime_comparison = certify_runtime()
    if (not runtime_comparison["model_visible_equal"]
            or runtime_comparison["ignored_transport_fields"]
            or runtime_comparison["original_raw_bytes_sha256"] != NEXT_SHA256
            or runtime_request != reconstructed):
        raise RuntimeError("Production runtime dry-run next request differs")
    if sha(runtime_request["messages"]) != "95737650e2f053901b01db20f9db9729e911cba395895d94713926cf2353556b":
        raise RuntimeError("Accepted provider-history request identity changed")
    working_state = {"key_info": working["call"]["args"]["key_info"], "passed_sessions": 0}
    if sha(working_state) != "bb0590c60c8033c9ba1e11e701cceae0e4429adcccd73d5ee7bbe912fd6c7d64":
        raise RuntimeError("Accepted working-state identity changed")

    write_json("SOURCE_MANIFEST.json", source_manifest())
    write_json("TURN30_BOUNDARY_TIMELINE.json", timeline())
    write_json("CHECKPOINT_WORKSPACE_MANIFEST.json", {"workspace_tree_sha256": workspace_tree,
                                                        "file_count": len(files),
                                                        "git_directory_certified_separately": True,
                                                        "files": files})
    write_json("GIT_STATE_CERTIFICATION.json", git_state)
    write_json("RUNTIME_CHECKPOINT_STATE.json", runtime_state)
    write_json("RUNTIME_NEXT_REQUEST_COMPARISON.json", runtime_comparison)
    (HERE / "PREVIOUS_REQUEST.json").write_bytes(request_path(PREVIOUS_ID).read_bytes())
    (HERE / "ORIGINAL_NEXT_REQUEST.json").write_bytes(request_path(NEXT_ID).read_bytes())
    write_json("RECONSTRUCTED_NEXT_REQUEST.json", runtime_request)
    write_json("NEXT_REQUEST_COMPARISON.json", request_comparison)
    history = provider_history_manifest(reconstructed["messages"])
    write_json("TASK_AGENT_PROVIDER_HISTORY_MANIFEST.json", history)
    key_info = working["call"]["args"]["key_info"]
    write_json("WORKING_CHECKPOINT.json", {
        "tool_call_id": working["call"]["id"], "exact_arguments": working["call"]["args"],
        "exact_result": working["result"], "backing_state": "Task Agent in-memory self.working",
        "checkpoint_relevant_state": working_state, "checkpoint_relevant_state_sha256": sha(working_state),
        "key_info_sha256": sha_bytes(key_info.encode("utf-8")),
        "next_prompt_sha256": sha_bytes(working["next_prompt"].encode("utf-8")),
        "visible_in_next_request": working["next_prompt"] == reconstructed["messages"][-1]["content"][-1]["text"],
        "next_request_form": "latest user content text block after tool_result",
    })
    leakage = {
        "included_model_visible_sources": ["clean task image /app public workspace at Git HEAD",
                                           "historical original-task sidecar from exact task bytes, public ls turn 2",
                                           "clean historical .git state (certified separately from workspace content SHA)",
                                           "successful public file writes/patches through turn 30",
                                           "exact Task turn-30 provider request history",
                                           "public Task turn-30 assistant tool call, result, next prompt",
                                           "original public task"],
        "excluded_future_private_evaluator_sources": ["public events archive_sequence >= 59",
                                                       "final pre-verification workspace contents",
                                                       "native verifier outputs and hidden tests",
                                                       "monitor private Task Book and dialogue",
                                                       "later reviewer outputs at 494495c",
                                                       "manual intervention and research interpretation"],
        "scan_method": "whitelist source lineage plus forbidden path/root check",
        "after_boundary_content_found": False,
        "future_information_excluded": True,
        "supervisor_intervention_between_tool_result_and_next_request": False,
        "prior_supervisor_interventions_in_history_are_not_removed": True,
        "historical_original_task_sidecar_allowed": ORIGINAL_TASK_SIDECAR,
        "historical_original_task_sidecar_sha256": EXPECTED[TASK],
        "git_directory_is_private_or_forbidden": False,
    }
    write_json("LEAKAGE_AUDIT.json", leakage)
    identity = {
        "validity": "eligible_exact", "source_commit": SOURCE_COMMIT,
        "task_id": "fyn-2.2.0-roadmap",
        "boundary": "post task-turn-30 tool result / pre next task-agent provider request",
        "workspace_tree_sha256": workspace_tree,
        "workspace_file_count": len(files),
        "git_state_certified": git_state["git_backed_workspace"],
        "runtime_state_certified": runtime_comparison["model_visible_equal"],
        "runtime_backend_history_sha256": runtime_state["backend_history_sha256"],
        "runtime_handler_history_info_sha256": runtime_state["history_info_sha256"],
        "task_agent_provider_history_sha256": history["history_sha256"],
        "working_state_sha256": sha(working_state),
        "original_next_request_model_visible_sha256": request_comparison["original_model_visible_sha256"],
        "reconstructed_next_request_model_visible_sha256": request_comparison["reconstructed_model_visible_sha256"],
        "model_visible_equal": True, "future_information_excluded": True,
        "boundary_intervention": False, "live_model_calls": 0,
        "native_evaluator_executed": False, "production_changes": 0,
        "materialized_workspace_local_path": str(MATERIALIZED),
    }
    write_json("CHECKPOINT_IDENTITY.json", identity)
    return identity


if __name__ == "__main__":
    print(json.dumps(freeze(), ensure_ascii=False))
