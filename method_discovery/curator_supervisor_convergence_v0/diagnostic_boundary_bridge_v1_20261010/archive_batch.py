"""Lossless, secret-checked archive of one complete or stopped static BJI batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile

from .freeze_inputs import HERE, digest
from .run_batch import ORDER
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009 import adapter
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009 import archive_static_batch as prior
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.freeze_run import HOST_PROFILE
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009 import freeze_inputs as origin


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def files_for(root, slots):
    rows = []
    for name in ("FROZEN_RUN_IDENTITY.json", "BATCH_PROGRESS.json", "BATCH_RESULT.json"):
        path = root / name
        if path.exists():
            rows.append((path, name))
    for path in list(root.glob("*.stdout")) + list(root.glob("*.stderr")):
        rows.append((path, path.relative_to(root).as_posix()))
    for slot in slots:
        base = root / slot["slot"]
        for name in ("BOOTSTRAP_STATE.json", "fixture/RESEARCH_ONLY_MANIFEST.json"):
            path = base / name
            if path.is_file():
                rows.append((path, path.relative_to(root).as_posix()))
        for sub in (base / "audit", base / "fixture/monitor_private",
                    base / "fixture/task_evidence"):
            if sub.exists():
                rows.extend((path, path.relative_to(root).as_posix()) for path in sub.rglob("*")
                            if path.is_file() and ".static_runtime" not in path.parts)
    fixed = [HERE / "freeze_inputs.py", HERE / "bootstrap.py", HERE / "payload_client.py",
             HERE / "ports.py", HERE / "native_runtime.py", HERE / "run_batch.py",
             HERE / "archive_batch.py", HERE / "EVALUATION_RECORD_TEMPLATE.json",
             HERE / "BOOTSTRAP_STATE_TEMPLATE.json",
             HERE / "frozen_requests/H_SOURCE_REQUEST.json",
             HERE / "frozen_requests/R_SOURCE_REQUEST.json",
             HERE / "frozen_requests/H_FULL_REQUEST.json",
             HERE / "frozen_requests/R_FULL_REQUEST.json",
             HERE / "frozen_requests/REQUEST_IDENTITY.json",
             adapter.HERE / "C02_VISIBILITY_MANIFEST.json",
             adapter.HERE / "ISOLATION_CERTIFICATION_V3.json"]
    rows.extend((path, "frozen_inputs/" +
                 (path.relative_to(HERE).as_posix() if path.is_relative_to(HERE) else path.name))
                for path in fixed)
    result = sorted(set(rows), key=lambda item: item[1])
    if len({name for _, name in result}) != len(result):
        raise RuntimeError("Archive member name collision")
    return result


def build(root: Path, destination: Path):
    if destination.exists():
        raise RuntimeError("Archive destination exists")
    batch = load(root / "BATCH_RESULT.json")
    slots = batch["slots"]
    planned = [f"C02-P{pair}-{arm}" for pair, first, second in ORDER for arm in (first, second)]
    if [item["slot"] for item in slots] != planned[:len(slots)]:
        raise RuntimeError("Started slot order differs from freeze")
    profile = load(HOST_PROFILE)["claude_monitor_opus48"]
    archived = load(origin.PROFILE)["claude_monitor_opus48"]
    secret_bytes = [value.encode("utf-8") for value in
                    (profile.get("apikey"), profile.get("apibase"),
                     archived.get("apikey"), archived.get("apibase"))
                    if isinstance(value, str) and value]
    source_files = files_for(root, slots)
    indexed = []
    for path, name in source_files:
        raw = path.read_bytes()
        if any(secret in raw for secret in secret_bytes):
            raise RuntimeError("Transport secret in selected archive member: " + name)
        indexed.append({"path": name, "bytes": len(raw), "sha256": digest(raw)})
    trace = {"source_commit": load(root / "FROZEN_RUN_IDENTITY.json")["source_commit"],
             "local_raw_root": str(root), "planned_slots": planned,
             "started_slots": [item["slot"] for item in slots],
             "unstarted_slots": planned[len(slots):],
             "selection": "raw provider/audit/private/public cutoff materials; not a full host snapshot",
             "excluded": ["per-slot disposable task-code copies (reconstructable from certified image and cutoff mutations)",
                          "runtime HOME/TMP/build caches and other scratch", "credentials and private endpoint"],
             "files": indexed, "slots": []}
    for slot in slots:
        path = root / slot["slot"] / "audit/events.jsonl"
        trace["slots"].append({**slot, "events": prior.event_index(path) if path.is_file()
                               else {"event_counts": {}, "locators": []}})
    destination.mkdir(parents=True)
    index = destination / "RAW_TRACE_INDEX.json"
    index.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive_path = destination / "RAW_TRAJECTORIES.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as archive:
        for path, name in source_files:
            archive.write(path, arcname=name)
        archive.write(index, arcname="RAW_TRACE_INDEX.json")
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Archive ZIP CRC failure")
        for row in indexed:
            raw = archive.read(row["path"])
            if len(raw) != row["bytes"] or digest(raw) != row["sha256"]:
                raise RuntimeError("ZIP member identity mismatch: " + row["path"])
    packet = destination / "H_R_NATIVE_BOUNDARY_AUDIT_PACKET.txt"
    with packet.open("w", encoding="utf-8", newline="\n") as output:
        output.write("C02 H/R NATIVE CRS/RHR/RER STATIC DIAGNOSTIC - MECHANICAL AUDIT PACK\n")
        output.write("Static Task; native Supervisor control; no real Task delivery or release.\n")
        output.write("No developer-side semantic quality or winner judgment is assigned.\n")
        output.write("Task Agent/native evaluator/training/scoring-model calls: 0. Production changes: 0.\n")
        output.write("RAW_TRACE_INDEX SHA-256: " + digest(index.read_bytes()) + "\n")
        output.write("RAW_TRAJECTORIES ZIP SHA-256: " + digest(archive_path.read_bytes()) + "\n")
        output.write("LOCAL RAW ROOT: " + str(root) + "\n")
        output.write("All UTF-8 archive members follow in full; non-text members remain in the verified ZIP.\n")
        for path, name in source_files:
            raw = path.read_bytes()
            output.write("\n===== " + name + " | bytes=" + str(len(raw)) +
                         " | sha256=" + digest(raw) + " =====\n")
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                output.write("[non-UTF-8 bytes; exact content in RAW_TRAJECTORIES.zip]\n")
            else:
                output.write(content)
                if not content.endswith("\n"):
                    output.write("\n")
    return {"started_slots": len(slots), "indexed_files": len(indexed),
            "index_sha256": digest(index.read_bytes()),
            "zip_sha256": digest(archive_path.read_bytes()),
            "packet_sha256": digest(packet.read_bytes())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.run_root.resolve(strict=True), args.destination), sort_keys=True))


if __name__ == "__main__":
    main()
