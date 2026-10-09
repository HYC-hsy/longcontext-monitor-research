"""Mechanical, secret-checked archive of a completed static diagnostic batch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from . import adapter
from .freeze_run import HOST_PROFILE
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009 import freeze_inputs


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def selected_files(root: Path, slots: list[dict]) -> list[Path]:
    files = [root / name for name in ("BATCH_PROGRESS.json", "BATCH_RESULT.json",
             "FROZEN_RUN_IDENTITY.json", "RAW_FILE_MANIFEST.json")]
    files += sorted(root.glob("*.stdout")) + sorted(root.glob("*.stderr"))
    for slot in slots:
        base = root / slot["slot"]
        files += sorted(path for path in (base / "audit").rglob("*") if path.is_file())
        files.append(base / "fixture/RESEARCH_ONLY_MANIFEST.json")
        private = base / "fixture/monitor_private"
        files += sorted(path for path in private.rglob("*") if path.is_file() and
                        ".static_runtime" not in path.relative_to(private).parts)
    files += [adapter.HERE / name for name in ("C01_B_STATIC_REQUEST.json",
              "C01_F_STATIC_REQUEST.json", "C02_B_STATIC_REQUEST.json",
              "C02_F_STATIC_REQUEST.json", "REQUEST_COMPARISON.json",
              "ISOLATION_CERTIFICATION_V3.json", "RUN_ORDER_AND_LIMITS.json")]
    return sorted(set(files), key=lambda path: str(path).lower())


def event_index(path: Path) -> dict:
    locators = []
    counts = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        item = json.loads(line)
        kind = item.get("kind")
        counts[kind] = counts.get(kind, 0) + 1
        if kind in {"provider_pre_send", "provider_response", "tool_execution",
                    "tool_validation_error", "tool_not_executed", "response_control_preflight",
                    "adapter_integrity_failure", "control_proposal", "loop_model_output",
                    "loop_tool_call", "loop_tool_result", "loop_control_result",
                    "failed_terminal", "budget_terminal"}:
            locators.append({"line": line_no, "kind": kind,
                             "content_sha256": digest(line.encode("utf-8")),
                             "request_index": item.get("index"),
                             "tool_name": item.get("name"),
                             "tool_id": item.get("tool_id")})
    return {"event_counts": counts, "locators": locators}


def build(root: Path, destination: Path, stage1_packet: Path) -> dict:
    if destination.exists():
        raise RuntimeError("Archive destination exists")
    batch = load(root / "BATCH_RESULT.json")
    if batch["started_count"] != batch["planned_count"] or batch["planned_count"] != 12:
        raise RuntimeError("Not a completed frozen batch")
    slots = batch["slots"]
    if [row["slot"] for row in slots] != [f"{scene}-R{rep}-{arm}_static"
            for scene, rep, first, second in adapter.ORDER for arm in (first, second)]:
        raise RuntimeError("Frozen slot order mismatch")
    profile = load(HOST_PROFILE)["claude_monitor_opus48"]
    archived = load(freeze_inputs.PROFILE)["claude_monitor_opus48"]
    secrets = [value.encode("utf-8") for value in (profile.get("apikey"),
               profile.get("apibase"), archived.get("apikey"), archived.get("apibase"))
               if isinstance(value, str) and value]
    source_files = selected_files(root, slots)
    hashes = []
    for path in source_files:
        if not path.is_file():
            raise RuntimeError("Raw artifact missing: " + path.name)
        raw = path.read_bytes()
        if any(secret in raw for secret in secrets):
            raise RuntimeError("Private transport material found in raw artifact: " + path.name)
        relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else \
                   "frozen_inputs/" + path.name
        hashes.append({"path": relative, "bytes": len(raw), "sha256": digest(raw)})
    index = {"source_commit": load(root / "FROZEN_RUN_IDENTITY.json")["source_commit"],
             "raw_root_local": str(root), "files": hashes, "slots": []}
    for slot in slots:
        base = root / slot["slot"]
        audit = base / "audit"
        event = event_index(audit / "events.jsonl")
        request_files = sorted(audit.glob("request_*.json"))
        stream_files = sorted(audit.glob("stream_*.sse"))
        if (slot["child_exit_code"] != 0 or len(request_files) != slot["provider_requests"] or
                len(stream_files) != slot["provider_requests"] or
                event["event_counts"].get("provider_response", 0) != slot["accepted_responses"]):
            raise RuntimeError("Slot transport/archive mismatch: " + slot["slot"])
        index["slots"].append({"slot": slot["slot"], "terminal": slot["terminal"],
                               "provider_requests": slot["provider_requests"],
                               "model_turns": slot["model_turns"], "accepted_responses": slot["accepted_responses"],
                               "tool_calls": slot["tool_calls"], "tool_polls": slot["tool_polls"],
                               "proposed_tool_calls": slot["proposed_tool_calls"],
                               "ordinary_port_calls": slot["ordinary_port_calls"],
                               "not_executed": slot["not_executed"],
                               "parameter_rejections": slot["parameter_rejections"],
                               "control_proposals": slot["control_proposals"],
                               "wall_seconds": slot["wall_seconds"], "usage": slot["usage"],
                               "events": event})
    destination.mkdir(parents=True)
    index_path = destination / "RAW_TRACE_INDEX.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    zip_path = destination / "RAW_TRAJECTORIES.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, row in zip(source_files, hashes):
            archive.write(path, arcname=row["path"])
        archive.write(index_path, arcname="RAW_TRACE_INDEX.json")
    freeze = load(root / "FROZEN_RUN_IDENTITY.json")
    lines = ["STATIC DIAGNOSTIC BATCH — MECHANICAL AUDIT PACK", "",
             "No B/F scientific ranking or correctness verdict is assigned here.",
             "Batch v1 remains immutable exploratory evidence affected by Windows LF-to-CRLF script writing.",
             "This batch v2 is independently frozen and is not pooled with v1.",
             "Historical online recovery: BLOCKED; static snapshot diagnosis only.",
             "Task Agent calls: 0; native evaluator calls: 0; training: 0; production changes: 0.",
             "", "FROZEN RUN IDENTITY (non-secret):",
             json.dumps(freeze, indent=2, ensure_ascii=False), "",
             "SLOT RESULTS (all started attempts retained):"]
    for row in index["slots"]:
        lines.append(json.dumps({key: value for key, value in row.items() if key != "events"},
                                ensure_ascii=False, sort_keys=True))
    lines += ["", "RAW EVIDENCE:",
              f"RAW_TRACE_INDEX.json SHA-256: {digest(index_path.read_bytes())}",
              f"RAW_TRAJECTORIES.zip SHA-256: {digest(zip_path.read_bytes())}",
              f"Original local run root: {root}",
              "ZIP includes full provider requests, raw SSE streams, event records, tool command receipts,",
              "per-attempt private notes, staged manifests, and batch results. Immutable task/evidence files",
              "are bound by the stage-1 visibility manifests; disposable build caches are excluded from ZIP",
              "but remain locally hashed in RAW_FILE_MANIFEST.json.",
              "", "TEST EVIDENCE:",
              "Changed-path zero-model tests: test_docker_tool 6/6, test_protocol 9/9,",
              "test_live_batch 3/3. certify_v2: both C01/C02 actual Docker probes passed.",
              "First-send host-profile assembly equaled frozen request; temperature omitted.",
              "", "UNRESOLVED/BOUNDARIES:",
              "Static environment is a common modification of historical online execution, not exact live replay.",
              "Host transport profile uses the same model-visible settings and route as archived profile,",
              "but different host-side endpoint/credential bytes; no endpoint or credential is included here.",
              "No native evaluator or Task continuation was run. Diagnostic quality requires separate review.",
              "", "STAGE-1 AUDIT PACKET (verbatim):", stage1_packet.read_text(encoding="utf-8")]
    packet = destination / "STATIC_DIAGNOSTIC_AUDIT_PACKET.txt"
    packet.write_text("\n".join(lines), encoding="utf-8")
    return {"index_sha256": digest(index_path.read_bytes()),
            "zip_sha256": digest(zip_path.read_bytes()),
            "packet_sha256": digest(packet.read_bytes()), "archived_files": len(hashes),
            "slots": len(slots)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--stage1-packet", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.run_root.resolve(strict=True), args.destination,
                           args.stage1_packet.resolve(strict=True)), sort_keys=True))


if __name__ == "__main__":
    main()
