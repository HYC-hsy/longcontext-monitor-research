"""Publish a credential-redacted, per-file readable archive of one fixed run."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

from upstream_memory_mechanism_diagnostic import PROFILE_HASH, profile_identity


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def redact(data: bytes, secrets: list[str]) -> bytes:
    # PowerShell's captured preflight console is UTF-16 with a BOM; model
    # requests and upstream JSON are UTF-8. Never guess a decoding without it.
    text = data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff"))
                       else "utf-8", errors="strict")
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED_PRIVATE_TRANSPORT]")
    text = re.sub(r"(?i)(api[_-]?key\s*[:=]\s*[\"']?)[^\s\"',}]+",
                  r"\1[REDACTED]", text)
    return text.encode("utf-8")


def archive(manifest_path: Path, run_root: Path, output: Path, profile_path: Path) -> dict:
    if output.exists():
        raise FileExistsError("archive target already exists")
    profile, _ = profile_identity(profile_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["profile_sha256"] != PROFILE_HASH or Path(manifest["output_root"]) != run_root:
        raise ValueError("run/profile binding differs")
    output.mkdir(parents=True)
    public = output / "raw_readable"
    public.mkdir()
    secrets = [profile.get("apikey", ""), profile.get("apibase", "")]
    candidates = [manifest_path] + sorted(path for path in run_root.rglob("*") if path.is_file())
    hashes = []
    for source in candidates:
        relative = Path("frozen_manifest.json") if source == manifest_path else source.relative_to(run_root)
        target = public / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        sanitized = redact(raw, secrets)
        if any(secret and secret.encode("utf-8") in sanitized for secret in secrets):
            raise ValueError("private transport data remains in archive")
        target.write_bytes(sanitized)
        hashes.append({"path": relative.as_posix(), "raw_private_sha256": sha(raw),
                       "uploaded_sha256": sha(sanitized), "uploaded_size": len(sanitized),
                       "redacted": raw != sanitized})
    results = [json.loads(line) for line in (run_root / "summary.jsonl").read_text(
        encoding="utf-8").splitlines()] if (run_root / "summary.jsonl").exists() else []
    condition_key = [{"blind_unit": row["unit_id"], "block": row["block"],
                      "condition": row["unit"], "status": row["status"]} for row in results]
    (output / "condition_key.json").write_text(json.dumps(condition_key, indent=2), encoding="utf-8")
    (output / "blind_index.txt").write_text("\n".join(
        f"{row['unit_id']}: raw_readable/{row['unit_id']}/requests.jsonl, responses.jsonl, "
        "provider_attempts.jsonl, bank_before.json, bank_after.json, result.json"
        for row in results), encoding="utf-8")
    (output / "FILE_HASHES.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    with zipfile.ZipFile(output / "raw_trajectories.zip", "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for file in public.rglob("*"):
            if file.is_file():
                bundle.write(file, file.relative_to(public))
    root = Path(__file__).resolve().parents[3]
    diff = subprocess.run(["git", "diff", "1aaa406475c47976ea93b7ab619b047f9d2ad150.." +
                           manifest["code_commit"], "--",
                           "method_discovery/curator_supervisor_convergence_v0/"
                           "pma_full_upstream_ga_v1_20261013"], cwd=root,
                          capture_output=True, text=True, encoding="utf-8", check=True).stdout
    completed = sum(row["status"] == "completed" for row in results)
    report = ["ORIGINAL PMA ARCHIVED-INPUT DIAGNOSTIC — MECHANICAL AUDIT",
              f"data commit: {manifest['data_commit']}",
              f"run code commit: {manifest['code_commit']}",
              f"batch ID: {manifest['batch_id']}",
              f"profile SHA-256: {PROFILE_HASH}",
              f"observed units: {len(results)}/40; completed: {completed}",
              f"logical calls observed: {sum(row.get('logical_calls', 0) for row in results)}",
              f"observable LiteLLM calls: {sum(row.get('observable_lower_calls', 0) for row in results)}",
              "deeper provider attempts: unknown unless transport records expose them",
              "Task/native evaluator/training/scoring-model calls: 0 (research entry has none)",
              "These are archived-input replays, not exact historical model sampling or Task effects.",
              "Condition mapping is separate from the numbered raw-material index.",
              "Human review fields: " + ", ".join(manifest["review_fields"]),
              "RESULTS:", json.dumps(results, ensure_ascii=False, indent=2),
              "VARIANT DIFFS:"]
    for label, value in manifest["variant_diffs"].items():
        report.extend((f"[{label}]", value or "(unchanged)"))
    report.extend(("CODE DIFF:", diff))
    (output / "AUDIT.txt").write_text("\n".join(report), encoding="utf-8")
    return {"completed": completed, "units_attempted": len(results),
            "uploaded_files": len(hashes), "archive_sha256": sha((output / "raw_trajectories.zip").read_bytes())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(archive(args.manifest, args.run_root, args.output, args.profile), sort_keys=True))


if __name__ == "__main__":
    main()
