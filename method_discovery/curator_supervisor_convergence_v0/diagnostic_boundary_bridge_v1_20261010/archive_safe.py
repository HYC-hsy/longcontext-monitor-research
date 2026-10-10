"""Post-run archive: preserve raw local files; redact transport secrets in export copies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
import zipfile

from .archive_batch import files_for, load
from .freeze_inputs import digest
from .run_batch import ORDER
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009 import archive_static_batch as prior
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.freeze_run import HOST_PROFILE
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009 import freeze_inputs as origin


def private_needles():
    needles = []
    for path in (HOST_PROFILE, origin.PROFILE):
        profile = load(path)["claude_monitor_opus48"]
        for key in ("apikey", "apibase"):
            value = profile.get(key)
            if isinstance(value, str) and value:
                needles.append((value.encode("utf-8"), "private_" + key))
        base = profile.get("apibase")
        host = urlparse(base).hostname if isinstance(base, str) else None
        if host:
            needles.append((host.encode("utf-8"), "private_endpoint_host"))
    return sorted(set(needles), key=lambda row: -len(row[0]))


def export_copy(raw: bytes, needles):
    exported = raw
    kinds = []
    for value, kind in needles:
        if value in exported:
            try:
                exported.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise RuntimeError("Secret appeared in non-text archive member") from exc
            exported = exported.replace(value, ("[REDACTED_" + kind.upper() + "]").encode())
            kinds.append(kind)
    if any(value in exported for value, _ in needles):
        raise RuntimeError("Transport secret remained after redaction")
    return exported, sorted(set(kinds))


def build(root: Path, destination: Path):
    if destination.exists():
        raise RuntimeError("Archive destination already exists")
    batch = load(root / "BATCH_RESULT.json")
    slots = batch["slots"]
    planned = [f"C02-P{pair}-{arm}" for pair, first, second in ORDER for arm in (first, second)]
    if [row["slot"] for row in slots] != planned[:len(slots)]:
        raise RuntimeError("Started slot order differs from freeze")
    needles = private_needles()
    source_files = files_for(root, slots)
    summary = root / "MECHANICAL_SUMMARY.json"
    if summary.is_file():
        source_files.append((summary, "MECHANICAL_SUMMARY.json"))
    source_files.sort(key=lambda row: row[1])
    copies, indexed = [], []
    for source, name in source_files:
        raw = source.read_bytes()
        exported, redactions = export_copy(raw, needles)
        copies.append((name, exported))
        indexed.append({"path": name, "source_bytes": len(raw),
                        "source_sha256": digest(raw), "archived_bytes": len(exported),
                        "archived_sha256": digest(exported), "redactions": redactions,
                        "raw_local_path": str(source) if redactions else None})
    trace = {"source_commit": load(root / "FROZEN_RUN_IDENTITY.json")["source_commit"],
             "local_raw_root": str(root), "planned_slots": planned,
             "started_slots": [row["slot"] for row in slots],
             "unstarted_slots": planned[len(slots):],
             "selection": "raw provider/audit/private/public cutoff materials; not a full host snapshot",
             "excluded": ["disposable Task-code copies reconstructable from certified image and cutoff mutations",
                          "runtime HOME/TMP/build caches/scratch", "credentials and private endpoint"],
             "redaction_policy": "Original raw files unchanged locally; exact endpoint/key occurrences in export copies replaced, with original hashes and paths recorded.",
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
        for name, exported in copies:
            archive.writestr(name, exported)
        archive.write(index, arcname="RAW_TRACE_INDEX.json")
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC failure")
        for row in indexed:
            raw = archive.read(row["path"])
            if len(raw) != row["archived_bytes"] or digest(raw) != row["archived_sha256"]:
                raise RuntimeError("ZIP member identity mismatch: " + row["path"])
    packet = destination / "H_R_NATIVE_BOUNDARY_AUDIT_PACKET.txt"
    with packet.open("w", encoding="utf-8", newline="\n") as output:
        output.write("C02 H/R native control-path static diagnostic - mechanical audit pack\n")
        output.write("No Task Agent, native evaluator, training, scorer model, or real Task control.\n")
        output.write("No developer-side quality label or H/R winner judgment.\n")
        output.write("Original raw logs remain unchanged at local_raw_root; exported secret redactions are indexed.\n")
        output.write("RAW_TRACE_INDEX SHA-256: " + digest(index.read_bytes()) + "\n")
        output.write("RAW_TRAJECTORIES ZIP SHA-256: " + digest(archive_path.read_bytes()) + "\n")
        for name, exported in copies:
            output.write("\n===== " + name + " | archived_bytes=" + str(len(exported)) +
                         " | sha256=" + digest(exported) + " =====\n")
            try:
                decoded = exported.decode("utf-8")
            except UnicodeDecodeError:
                output.write("[binary member: exact bytes in verified ZIP]\n")
            else:
                output.write(decoded)
                if not decoded.endswith("\n"):
                    output.write("\n")
    return {"started_slots": len(slots), "indexed_files": len(indexed),
            "redacted_members": [row["path"] for row in indexed if row["redactions"]],
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
