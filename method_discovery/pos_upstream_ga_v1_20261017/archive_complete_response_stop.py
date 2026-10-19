"""Archive the stopped two-task complete-response batch; never resumes execution."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .archive_formal_v6_stop import public
from .archive_remaining_stop import archive_line_file, digest
from .collect_native_shared import secrets_from_profile


def selection(source: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    if list(source.glob("*/authorization.json")):
        raise RuntimeError("active authorization remains")
    first = source / "01_adaptive-rejection-sampler"
    second = source / "02_write-compressor"
    identity = json.loads((first / "run_identity.json").read_text(encoding="utf-8"))
    run = Path(identity["run_root"]).resolve(strict=True)
    if not run.is_relative_to(first.resolve(strict=True)) or run.name != identity["run_id"]:
        raise RuntimeError("sampler run identity mismatch")
    if (second / "serial_start.json").exists() or (second / "authorization.json").exists():
        raise RuntimeError("compressor was started or authorized")
    trials = [path for path in (run / "jobs").glob("*/*") if
              (path / "agent/research_events.jsonl").is_file()]
    if len(trials) != 1:
        raise RuntimeError("Task trial not unique")
    trial = trials[0]
    files: dict[str, Path] = {"scope/scope.json": source / "scope.json"}
    for name in ("prepare_01.json", "prepare_02.json"):
        files["scope/" + name] = source / name
    for base, prefix, names in (
        (first, "01", ("manifest.json", "plan.json", "run_identity.json",
                       "serial_start.json", "serial_result.json", "authorization_removed.json",
                       "serial_stderr.txt", "batch_result.json")),
        (second, "02_prepared_only", ("manifest.json", "plan.json", "run_identity.json")),
    ):
        for name in names:
            path = base / name
            if path.is_file():
                files[f"{prefix}/{name}"] = path
    for name in ("agent_start_identity.json", "agent_end_native.json",
                 "control_process_registry.json", "live_command_public.json", "live_result.json",
                 "native_evaluator_uploaded.json", "native_reports_checked.json",
                 "native_test_execution.json", "pos_archive_status.json", "prepared.json",
                 "verification_released.json", "writer_termination_check.json"):
        path = run / "archive" / name
        if path.is_file():
            files[f"01/archive/{name}"] = path
    for name in ("events.host.jsonl", "events.bridge.jsonl", "events.stderr.log",
                 "events.close.json"):
        path = run / "control/pos_archive" / name
        if path.is_file():
            files[f"01/pos/{name}"] = path
    for name in ("research_events.jsonl", "task_terminal.json", "agent_stdout.log",
                 "agent_stderr.log", "agent_process_return_code.txt"):
        path = trial / "agent" / name
        if path.is_file():
            files[f"01/task/{name}"] = path
    for name in ("result.json", "verifier/ctrf.json", "verifier/reward.txt",
                 "verifier/test-stdout.txt"):
        path = trial / name
        if path.is_file():
            files[f"01/task/{name}"] = path
    provider = run / "control/pos_archive/events.provider.jsonl"
    if provider.is_file():
        files["01/pos/events.provider.jsonl"] = provider
    omitted = {
        "01/pos/events.jsonl": run / "control/pos_archive/events.jsonl",
        "01/pos/events.result.json": run / "control/pos_archive/events.result.json",
        "01/serial_stdout.txt": first / "serial_stdout.txt",
    }
    return files, omitted


def role_metadata(path: Path, target: Path) -> tuple[int, str]:
    """Emit a safe event chronology, not a substitute for the private full state."""
    digest_state = hashlib.sha256()
    with path.open(encoding="utf-8", errors="replace") as original, target.open("xb") as output:
        for number, line in enumerate(original, 1):
            row = json.loads(line)
            projected = {"source_line": number, "time": row.get("time"),
                         "event": row.get("event")}
            for key in ("role", "step", "operation", "command", "call_id",
                        "attempt", "status", "success", "run_id", "task_id"):
                value = row.get(key)
                if value is None or isinstance(value, (bool, int, float)) or (
                        isinstance(value, str) and len(value) <= 120):
                    projected[key] = value
            data = (json.dumps(projected, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
            output.write(data)
            digest_state.update(data)
    return target.stat().st_size, digest_state.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--task-profile", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    files, omitted = selection(source)
    secrets = secrets_from_profile(args.task_profile)
    args.target.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, path in sorted(files.items()):
        if path.suffix == ".jsonl":
            rows.append(archive_line_file(name, path, args.target, secrets))
            continue
        size, source_sha = digest(path)
        try:
            data, redactions = public(path.read_bytes(), secrets)
        except (ValueError, UnicodeError):
            rows.append({"path": name, "source_bytes": size, "source_sha256": source_sha,
                         "public_parts": [], "redactions": 0,
                         "omissions": [{"reason": "unsafe_public_projection"}]})
            continue
        output = args.target / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        rows.append({"path": name, "source_bytes": size, "source_sha256": source_sha,
                     "public_parts": [{"path": name, "bytes": len(data),
                                       "sha256": hashlib.sha256(data).hexdigest()}],
                     "redactions": redactions, "omissions": []})
    role_source = omitted["01/pos/events.jsonl"]
    role_output = args.target / "01/pos/role_event_metadata.jsonl"
    role_output.parent.mkdir(parents=True, exist_ok=True)
    role_bytes, role_sha = role_metadata(role_source, role_output)
    rows.append({"path": "01/pos/role_event_metadata.jsonl", "derived_from": "01/pos/events.jsonl",
                 "public_parts": [{"path": "01/pos/role_event_metadata.jsonl",
                                   "bytes": role_bytes, "sha256": role_sha}],
                 "redactions": 0, "omissions": []})
    private_only = []
    for name, path in omitted.items():
        if path.is_file():
            size, source_sha = digest(path)
            private_only.append({"path": name, "source_bytes": size,
                                 "source_sha256": source_sha,
                                 "reason": "large_private_original; public metadata or bounded records provided"})
    index = {"schema": "pos-ga-complete-response-stop-public-v1", "source": str(source),
             "public_copy_is_byte_identical_to_source": False,
             "files": rows, "private_only": private_only}
    index_path = args.target / "FILE_HASHES.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")
    for row in rows:
        for part in row["public_parts"]:
            if digest(args.target / part["path"]) != (part["bytes"], part["sha256"]):
                raise RuntimeError("public readback mismatch: " + part["path"])
    print(json.dumps({"files": len(rows), "private_only": len(private_only),
                      "omissions": sum(len(row["omissions"]) for row in rows),
                      "redactions": sum(row["redactions"] for row in rows),
                      "index_sha256": digest(index_path)[1]}))


if __name__ == "__main__":
    main()
