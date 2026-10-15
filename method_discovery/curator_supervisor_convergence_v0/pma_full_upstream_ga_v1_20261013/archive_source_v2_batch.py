"""Redact and index a stopped S2/R2 static batch; never used as model input."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

from static_source_live import profile_identity
from static_source_screen import BATCH_SCHEMA, HERE, plan_slots, sha256


TEXT_EXTENSIONS = {".json", ".jsonl", ".txt", ".log", ".tsv", ".md"}


def redact(data: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            data = data.replace(secret, "<REDACTED_PRIVATE_TRANSPORT>")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--run-code-commit", required=True)
    parser.add_argument("--comparison-baseline", help="optional explicit diff base")
    parser.add_argument("--gate-stdout", type=Path)
    parser.add_argument("--gate-stderr", type=Path)
    parser.add_argument("--gate-exit", type=Path)
    parser.add_argument("--console", type=Path)
    args = parser.parse_args()
    if args.archive_root.exists():
        raise FileExistsError("archive destination must be new")
    profile, safe = profile_identity(args.profile)
    secrets = [profile["apikey"], profile["apibase"]]
    archive = args.archive_root
    raw = archive / "raw"
    raw.mkdir(parents=True)
    if args.run_root.exists():
        for source in sorted(path for path in args.run_root.rglob("*") if path.is_file()):
            relative = source.relative_to(args.run_root)
            target = raw / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix.lower() in TEXT_EXTENSIONS:
                content = redact(source.read_text(encoding="utf-8", errors="replace"), secrets)
                target.write_text(content, encoding="utf-8")
            else:
                shutil.copyfile(source, target)
    for name, path in (("gate_stdout.txt", args.gate_stdout),
                       ("gate_stderr.txt", args.gate_stderr),
                       ("gate_exit.txt", args.gate_exit),
                       ("console.txt", args.console)):
        if path is not None and path.exists():
            (archive / name).write_text(redact(path.read_text(encoding="utf-8", errors="replace"),
                                             secrets), encoding="utf-8")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    (archive / "FROZEN_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_file = raw / "summary.json"
    rows = json.loads(summary_file.read_text(encoding="utf-8")) if summary_file.exists() else []
    expected = manifest["run_bindings"]
    is_v3 = manifest.get("schema") == BATCH_SCHEMA
    slots = (plan_slots(manifest) if is_v3 or "cases" in manifest else
             [{"case_id": b["task"], "variant": b["variant"], "occurrence": 1}
              for b in expected])
    by_order = {row["order"]: row for row in rows}
    table = []
    for binding, identity in zip(expected, slots, strict=True):
        row = by_order.get(binding["order"])
        slot_dir = raw / binding["run_id"]
        requests = slot_dir / "requests.jsonl"
        started = slot_dir.exists() or row is not None
        observed = (len(requests.read_text(encoding="utf-8").splitlines())
                    if requests.is_file() else "unknown" if started else 0)
        table.append({"order": binding["order"], "task": binding["task"],
                      "variant": binding["variant"], "occurrence": identity["occurrence"],
                      "run_id": binding["run_id"],
                      "status": row["status"] if row else "started_incomplete" if started else "not_started",
                      "logical_calls": row.get("logical_phase_calls") if row else observed,
                      "observable_litellm_calls": row.get("observable_litellm_calls") if row else "unknown" if started else 0,
                      "error_type": row.get("error_type") if row else None})
    (archive / "SLOT_SUMMARY.json").write_text(json.dumps(table, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
    samples = []
    for binding in expected:
        request_file = raw / binding["run_id"] / "requests.jsonl"
        if request_file.exists():
            with request_file.open(encoding="utf-8") as stream:
                first = [json.loads(line) for _, line in zip(range(2), stream)]
            samples.append({"order": binding["order"], "variant": binding["variant"],
                            "first_two_logical_requests": first})
    (archive / "REQUEST_SAMPLES.txt").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    diff = (subprocess.run(["git", "diff", args.comparison_baseline, args.run_code_commit, "--",
        "method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013"],
        cwd=HERE, capture_output=True, text=True, check=True).stdout
        if args.comparison_baseline else "(comparison baseline not supplied; no diff asserted)")
    case_ids = sorted({slot["case_id"] for slot in slots})
    variants = sorted({slot["variant"] for slot in slots})
    lines = ["S2/R2 STATIC PMA ENGINEERING AUDIT", "",
             "Nature: fixed exposed Task trajectory shadow screen; no Task delivery or native score.",
             f"Comparison baseline: {args.comparison_baseline or 'not supplied'}",
             f"Run code commit: {args.run_code_commit}",
             f"Manifest SHA-256: {sha256(args.manifest)}",
             f"Plan: {len(slots)} ordered slots, {len(case_ids)} cases {case_ids}, variants {variants}",
             f"Profile public identity: {json.dumps(safe, sort_keys=True)}",
             "Task/native evaluator/training/scoring-model calls: 0 by static entry design;",
             "observable LiteLLM lower-bound calls are listed by slot, inner network attempts remain unknown.",
             "Selected fixed public cutoffs are verified before send.",
             "Method paths present in this plan: " + ", ".join(variants) + ".",
             "No semantic quality verdict is made here.",
             "No candidate reminders were delivered to a Task Agent.", "",
             "SLOTS", json.dumps(table, ensure_ascii=False, indent=2), "",
             "REUSE MAP", (HERE / "REUSE_MAP_SOURCE_MEMORY_V2.json").read_text(encoding="utf-8"),
             "", "READABLE FIRST REQUESTS", (archive / "REQUEST_SAMPLES.txt").read_text(encoding="utf-8"),
             "",
             "COMPLETE IMPLEMENTATION DIFF", diff]
    for name in ("gate_stdout.txt", "gate_stderr.txt", "gate_exit.txt"):
        file = archive / name
        if file.exists():
            lines.extend(["", name, file.read_text(encoding="utf-8")])
    (archive / "AUDIT_COMPLETE.txt").write_text("\n".join(lines), encoding="utf-8")
    zip_path = archive / ("raw_trajectories.zip" if is_v3 else "raw_six_slots.zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for file in sorted(path for path in raw.rglob("*") if path.is_file()):
            bundle.write(file, file.relative_to(raw).as_posix())
    hashes = []
    for file in sorted(path for path in archive.rglob("*") if path.is_file()):
        hashes.append(f"{hashlib.sha256(file.read_bytes()).hexdigest()}\t{file.stat().st_size}\t{file.relative_to(archive).as_posix()}")
    (archive / "FILE_HASHES.tsv").write_text("sha256\tbytes\trelative_path\n" +
                                                "\n".join(hashes) + "\n", encoding="utf-8")
    for file in archive.rglob("*"):
        if file.is_file() and file.suffix.lower() in TEXT_EXTENSIONS:
            content = file.read_text(encoding="utf-8", errors="replace")
            if any(secret and secret in content for secret in secrets):
                raise RuntimeError(f"private transport value remained in {file.relative_to(archive)}")
    print(json.dumps({"archive": str(archive), "files": len(hashes),
                      "slots_started": len(rows), "zip_sha256": sha256(zip_path)}))


if __name__ == "__main__":
    main()
