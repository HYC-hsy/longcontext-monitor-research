"""One-off mechanical, redacted archive of the stopped six-task batch.

The original run tree remains private and unchanged. This script never resumes
an agent or evaluator, and does not infer task quality from native rewards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def private_values(task_profile: Path, pma_profile: Path) -> list[str]:
    values: set[str] = set()

    def collect(obj: object) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                lower = str(key).lower()
                if (isinstance(value, str) and len(value) >= 6 and
                        any(word in lower for word in
                            ("api_key", "secret", "password", "token", "api_base", "base_url"))):
                    values.add(value)
                else:
                    collect(value)
        elif isinstance(obj, (list, tuple)):
            for value in obj:
                collect(value)

    collect(runpy.run_path(str(task_profile))["native_claude_cc_vibe_opus48"])
    collect(json.loads(pma_profile.read_text(encoding="utf-8"))["claude_monitor_opus48"])
    return sorted(values, key=len, reverse=True)


def redact(raw: bytes, secrets: list[str]) -> tuple[bytes, int]:
    text = raw.decode("utf-8", errors="replace")
    changes = 0
    for secret in secrets:
        count = text.count(secret)
        if count:
            text = text.replace(secret, "[REDACTED_PRIVATE_CONFIG]")
            changes += count
    for pattern in (r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+",
                    r"(?i)([\"'](?:api_key|access_token|secret|password)[\"']\s*:\s*[\"'])[^\"']+"):
        text, count = re.subn(pattern, r"\1[REDACTED]", text)
        changes += count
    if any(secret in text for secret in secrets):
        raise RuntimeError("private config value remains after redaction")
    return text.encode("utf-8"), changes


def selected(root: Path, arm: int) -> list[Path]:
    base = root / "arms" / f"{arm:02d}"
    paths = list((base / "archive").glob("*"))
    paths += list((base / "host_private" / "archive").glob("*"))
    paths += list((base / "control" / "spool").rglob("*.json"))
    paths += list((base / "control" / "spool").rglob("*.jsonl"))
    paths += list((base / "jobs").glob("*/result.json"))
    paths += list((base / "jobs").glob("*/*/result.json"))
    paths += list((base / "jobs").glob("*/*/agent/*"))
    paths += list((base / "jobs").glob("*/*/verifier/*"))
    return sorted({p for p in paths if p.is_file()})


def summarize(root: Path) -> dict:
    batch = json.loads((root / "control" / "BATCH_RESULT.json").read_text(encoding="utf-8"))
    output = []
    for row in batch["arms"]:
        base = Path(row["run_root"])
        status = row["status"]
        job = list((base / "jobs").glob("*/*/result.json"))
        result = json.loads(job[0].read_text(encoding="utf-8")) if len(job) == 1 else {}
        events = list((base / "jobs").glob("*/*/agent/research_events.jsonl"))
        counts: dict[str, int] = {}
        tool_uses = 0
        usage = {"input_tokens": 0, "output_tokens": 0,
                 "cached_input_tokens": 0, "cache_creation_input_tokens": 0}
        termination = None
        if len(events) == 1:
            for line in events[0].read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                kind = event.get("event_type", "unknown")
                counts[kind] = counts.get(kind, 0) + 1
                if kind == "provider_usage":
                    for key in usage:
                        usage[key] += event.get("payload", {}).get(key, 0) or 0
                elif kind == "termination":
                    termination = event.get("payload", {}).get("result")
                elif kind == "action_selected":
                    tool_uses += len(event.get("payload", {}).get("tool_call_ids") or [])
        memory = base / "host_private" / "archive" / "memory_transport.jsonl"
        phases: dict[str, int] = {}
        if memory.is_file():
            for line in memory.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                kind = event.get("phase", "unknown") + ":" + event.get("status", "unknown")
                phases[kind] = phases.get(kind, 0) + 1
        output.append({"order": row["order"], "run_id": row["run_id"],
            "task": status.get("task"), "condition": status.get("condition"),
            "disposition": row["disposition"], "launcher_exit": row["launcher_exit"],
            "task_terminal": termination,
            "agent_execution": status.get("native_result", {}).get("agent_execution"),
            "provider_events": counts, "task_usage_visible": usage,
            "task_tool_uses_selected": tool_uses,
            "pma_phase_results": phases, "pma_finalization": status.get("pma_finalization"),
            "native_result": status.get("native_result"),
            "native_reward": ((result.get("verifier_result") or {}).get("rewards") or {}).get("reward"),
            "cleanup_confirmed": status.get("cleanup_confirmed"),
            "remaining_containers": status.get("remaining_containers"),
            "cleanup_errors": status.get("cleanup_errors")})
    return {"schema": "pma-ga-live-mechanical-summary-v2",
            "attempted": len(batch["arms"]), "not_started": batch["not_started"],
            "stop_reason": batch["stop_reason"], "arms": output}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--task-profile", type=Path, required=True)
    parser.add_argument("--pma-profile", type=Path, required=True)
    parser.add_argument("--resume-summary-only", action="store_true")
    args = parser.parse_args()
    root = args.run_root.resolve(strict=True)
    target = args.archive_root.resolve(strict=False)
    if args.resume_summary_only:
        if not (target / "FULL_LOCAL_FILE_INDEX.json").is_file() or not (
                target / "ARCHIVED_FILE_INDEX.json").is_file():
            raise RuntimeError("incomplete archive indices cannot be resumed")
        (target / "MECHANICAL_SUMMARY.json").write_text(
            json.dumps(summarize(root), indent=2, ensure_ascii=False), encoding="utf-8")
        print("SUMMARY_RESUMED")
        return
    if target.exists():
        raise FileExistsError(target)
    source_files = sorted(p for p in root.rglob("*") if p.is_file())
    private_index = [{"path": p.relative_to(root).as_posix(), "bytes": p.stat().st_size,
                      "sha256": sha(p)} for p in source_files]
    secrets = private_values(args.task_profile, args.pma_profile)
    chosen = [root / "control" / "BATCH_RESULT.json",
              root / "control" / "AUTHORIZATION.json"]
    if root.name == "pma-ga-six-batch-20261014-r1":
        for file in ("result.json", "task_response.json", "task_sse.jsonl",
                     "task_transport.jsonl", "pma_transport.jsonl", "pma_phase_errors.json"):
            candidate = root.parent / "pma-ga-six-compat-20261014-r1" / file
            if candidate.is_file():
                chosen.append(candidate)
    batch = json.loads((root / "control" / "BATCH_RESULT.json").read_text(encoding="utf-8"))
    for arm in (int(row["order"]) for row in batch["arms"]):
        chosen.extend(selected(root, arm))
    target.mkdir(parents=True)
    archived = []
    for source in sorted(set(chosen)):
        if source.is_relative_to(root):
            relative = source.relative_to(root)
        else:
            relative = Path("compatibility") / source.name
        destination = target / "raw" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        data, changes = redact(source.read_bytes(), secrets)
        destination.write_bytes(data)
        archived.append({"path": (Path("raw") / relative).as_posix(),
                         "source_bytes": source.stat().st_size,
                         "source_sha256": sha(source), "archive_bytes": len(data),
                         "archive_sha256": hashlib.sha256(data).hexdigest(),
                         "redactions": changes})
    (target / "FULL_LOCAL_FILE_INDEX.json").write_text(
        json.dumps(private_index, indent=2, ensure_ascii=False), encoding="utf-8")
    (target / "ARCHIVED_FILE_INDEX.json").write_text(
        json.dumps(archived, indent=2, ensure_ascii=False), encoding="utf-8")
    (target / "MECHANICAL_SUMMARY.json").write_text(
        json.dumps(summarize(root), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"full_local_files": len(private_index),
                      "archived_files": len(archived),
                      "redactions": sum(row["redactions"] for row in archived)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
