"""Mechanical secret-checked H/R raw archive, including partial stopped batches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile

from .projection import HERE, digest
from .run_batch import ORDER
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009 import adapter
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009 import archive_static_batch as v2archive
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.freeze_run import HOST_PROFILE
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009 import freeze_inputs


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def files_for(root: Path, slots: list[dict]) -> list[tuple[Path, str]]:
    paths = [(root / name, name) for name in ("FROZEN_RUN_IDENTITY.json", "BATCH_PROGRESS.json",
                                               "BATCH_RESULT.json", "RAW_FILE_MANIFEST.json")
             if (root / name).exists()]
    paths += [(path, path.relative_to(root).as_posix())
              for path in list(root.glob("*.stdout")) + list(root.glob("*.stderr"))]
    for slot in slots:
        base = root / slot["slot"]
        for sub in (base / "audit", base / "fixture/monitor_private"):
            if sub.exists():
                paths += [(path, path.relative_to(root).as_posix()) for path in sub.rglob("*")
                          if path.is_file() and ".static_runtime" not in path.relative_to(sub).parts]
        staged = base / "fixture/RESEARCH_ONLY_MANIFEST.json"
        if staged.exists():
            paths.append((staged, staged.relative_to(root).as_posix()))
    frozen = [HERE / "projection.py", HERE / "run_batch.py", HERE / "archive_batch.py",
              HERE / "EVALUATION_RECORD_TEMPLATE.json", HERE / "frozen_requests/H_REQUEST.json",
              HERE / "frozen_requests/R_REQUEST.json", HERE / "frozen_requests/PROJECTION_MANIFEST.json",
              adapter.HERE / "C02_VISIBILITY_MANIFEST.json",
              adapter.HERE / "ISOLATION_CERTIFICATION_V3.json"]
    paths += [(path, "frozen_inputs/" + path.relative_to(HERE).as_posix()
               if path.is_relative_to(HERE) else "frozen_inputs/" + path.name) for path in frozen]
    return sorted(set(paths), key=lambda item: item[1])


def build(root: Path, destination: Path) -> dict:
    if destination.exists():
        raise RuntimeError("Archive destination already exists")
    batch = load(root / "BATCH_RESULT.json")
    slots = batch["slots"]
    planned = [f"C02-P{pair}-{arm}" for pair, first, second in ORDER for arm in (first, second)]
    if [row["slot"] for row in slots] != planned[:len(slots)]:
        raise RuntimeError("Started slot order mismatch")
    profile = load(HOST_PROFILE)["claude_monitor_opus48"]
    archived = load(freeze_inputs.PROFILE)["claude_monitor_opus48"]
    secrets = [value.encode() for value in (profile.get("apikey"), profile.get("apibase"),
               archived.get("apikey"), archived.get("apibase")) if isinstance(value, str) and value]
    files = files_for(root, slots)
    rows = []
    for path, relative in files:
        if not path.is_file():
            raise RuntimeError("Missing archived artifact: " + relative)
        raw = path.read_bytes()
        if any(secret in raw for secret in secrets):
            raise RuntimeError("Private transport data in artifact: " + relative)
        rows.append({"path": relative, "bytes": len(raw), "sha256": digest(raw)})
    index = {"source_commit": load(root / "FROZEN_RUN_IDENTITY.json")["source_commit"],
             "local_raw_root": str(root), "planned_slots": planned,
             "started_slots": [row["slot"] for row in slots], "files": rows, "slots": []}
    for slot in slots:
        event_path = root / slot["slot"] / "audit/events.jsonl"
        if event_path.exists():
            events = v2archive.event_index(event_path)
        else:
            events = {"event_counts": {}, "locators": []}
        index["slots"].append({**slot, "events": events})
    destination.mkdir(parents=True)
    index_path = destination / "RAW_TRACE_INDEX.json"
    index_path.write_bytes((json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode())
    zip_path = destination / "RAW_TRAJECTORIES.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for (path, relative) in files:
            archive.write(path, arcname=relative)
        archive.write(index_path, arcname="RAW_TRACE_INDEX.json")
    packet = destination / "H_R_STATIC_DIAGNOSTIC_AUDIT_PACKET.txt"
    packet.write_text("\n".join([
        "C02 H/R STATIC HISTORY PROJECTION — MECHANICAL AUDIT PACK",
        "No semantic winner or diagnostic correctness verdict is assigned.",
        "H retains all 96 frozen C02 B messages. R renders early retained blocks as reversible",
        "records in one user message and preserves native messages 88–95 exactly.",
        "R removes only separable early assistant thinking/free text; historical interventions,",
        "command comments and private-memory writes may still carry earlier judgments.",
        "Role, length and information position changes are part of this context strategy.",
        "This is static diagnosis, not online opportunity discovery or Task outcome evidence.",
        "Task Agent/native evaluator/training calls: 0. Production changes: 0.",
        "", "FROZEN IDENTITY:", json.dumps(load(root / "FROZEN_RUN_IDENTITY.json"), ensure_ascii=False, indent=2),
        "", "ALL STARTED SLOT RESULTS:",
        *[json.dumps(row, ensure_ascii=False, sort_keys=True) for row in slots],
        "", "ARCHIVE INDEX SHA-256: " + digest(index_path.read_bytes()),
        "ZIP SHA-256: " + digest(zip_path.read_bytes()),
        "LOCAL RAW ROOT: " + str(root),
        "UNSTARTED SLOTS: " + json.dumps(planned[len(slots):]),
        "Evaluation dimensions are frozen in EVALUATION_RECORD_TEMPLATE.json and require",
        "independent post hoc review with raw event locators. No scorer model ran.",
    ]), encoding="utf-8")
    return {"started": len(slots), "files": len(rows),
            "index_sha256": digest(index_path.read_bytes()),
            "zip_sha256": digest(zip_path.read_bytes()),
            "packet_sha256": digest(packet.read_bytes())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.run_root.resolve(strict=True), args.destination), sort_keys=True))


if __name__ == "__main__":
    main()
