"""Export the completed retry batch without copying credentials or live bundles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import runpy
import tarfile
import zipfile


STAGE = Path(__file__).resolve().parent
SOURCE = Path("E:/pma-ga-live-batch-retry-20261014")
DEST = STAGE / "live_batch_retry_20261014"
ARMS = ("db_a", "db_b", "code_b", "code_a")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def secrets() -> list[bytes]:
    task = runpy.run_path("E:/LongContext/GenericAgent-main/mykey.py")[
        "native_claude_cc_vibe_opus48"]
    monitor = json.loads(Path("E:/LongContext/monitor_config/models.local.json")
                         .read_text(encoding="utf-8"))["claude_monitor_opus48"]
    values = {str(profile[key]).encode("utf-8") for profile in (task, monitor)
              for key in ("apikey", "apibase") if profile.get(key)}
    return sorted(values, key=len, reverse=True)


def sanitize(raw: bytes, private: list[bytes]) -> bytes:
    for value in private:
        raw = raw.replace(value, b"[REDACTED_PRIVATE_CONFIG]")
    text = raw.decode("utf-8", "replace")
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}\b", "[REDACTED_KEY]", text)
    text = re.sub(r'(?i)("(?:authorization|x-api-key|api_key|apikey)"\s*:\s*")[^"]+',
                  r'\1[REDACTED]', text)
    text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~-]{12,}",
                  r"\1[REDACTED]", text)
    return text.encode("utf-8")


def selected() -> list[Path]:
    paths = list((SOURCE / "compatibility").rglob("*"))
    paths.append(SOURCE / "control" / "BATCH_RESULT.json")
    for arm in ARMS:
        root = SOURCE / "arms" / arm
        for name in ("archive", "jobs"):
            paths.extend((root / name).rglob("*"))
        paths.extend((root / "control" / "spool").rglob("*"))
        paths.extend((root / "host_private" / "archive").rglob("*"))
        paths.append(root / "host_private" / "worker_exit.json")
        paths.append(root / "control" / "harbor_spec.json")
        paths.append(root / "control" / "sidecar_stopped.json")
    return sorted({p for p in paths if p.is_file()})


def validate_product(path: Path, private: list[bytes]) -> None:
    with tarfile.open(path) as archive:
        for member in archive.getmembers():
            if (member.name.startswith("/") or ".." in Path(member.name).parts or
                    not (member.isfile() or member.isdir())):
                raise RuntimeError(f"unsafe frozen product member: {member.name}")
            if member.isfile():
                body = archive.extractfile(member).read()
                if any(value in body for value in private):
                    raise RuntimeError(f"private configuration in frozen product: {member.name}")
                if re.search(rb"\bsk-[A-Za-z0-9_-]{12,}\b", body):
                    raise RuntimeError(f"key-like text in frozen product: {member.name}")


def summary() -> dict:
    batch = json.loads((SOURCE / "control" / "BATCH_RESULT.json")
                       .read_text(encoding="utf-8"))
    record = {"execution_commit": "e8a351cbb2006f056ab7faac1754280cc02396e1",
              "source_root": str(SOURCE), "batch_stop_reason": batch["stop_reason"],
              "not_started": len(batch["not_started"]), "arms": []}
    for arm in batch["arms"]:
        root = Path(arm["run_root"])
        events = [json.loads(line) for path in (root / "jobs").rglob("research_events.jsonl")
                  for line in path.read_text(encoding="utf-8").splitlines()]
        count = lambda name: sum(row["event_type"] == name for row in events)
        usage = {key: sum(int(row["payload"].get(key) or 0) for row in events
                          if row["event_type"] == "provider_usage")
                 for key in ("input_tokens", "output_tokens",
                             "cache_creation_input_tokens", "cache_read_input_tokens")}
        proposed = sum(len(row["payload"].get("tool_call_ids") or []) for row in events
                       if row["event_type"] == "action_selected")
        terminal_files = list((root / "jobs").rglob("task_terminal.json"))
        terminal = json.loads(terminal_files[0].read_text(encoding="utf-8"))
        frozen = json.loads((root / "archive" / "agent_end_frozen.json")
                            .read_text(encoding="utf-8"))
        rewards = [path.read_text(encoding="utf-8").strip()
                   for path in (root / "jobs").rglob("reward.txt")]
        phases = list((root / "host_private" / "archive").glob("memory_transport.jsonl"))
        pma = [json.loads(line) for path in phases
               for line in path.read_text(encoding="utf-8").splitlines()]
        record["arms"].append({
            "order": arm["order"], "run_id": arm["run_id"],
            "disposition": arm["disposition"], "launcher_exit": arm["launcher_exit"],
            "harbor_exit": arm["status"]["harbor_return_code"],
            "worker_exit": arm["status"]["worker_return_code"],
            "cleanup_confirmed": arm["status"]["cleanup_confirmed"],
            "remaining_containers": arm["status"]["remaining_containers"],
            "task_terminal_record": terminal,
            "frozen_terminal": frozen["task_terminal"],
            "legal_agent_end": frozen["legal_agent_end"],
            "frozen_product_sha256": frozen["tar_sha256"],
            "native_reward": rewards[0] if rewards else None,
            "native_score_unavailable_reason": None if rewards else
                "completion identity gate denied evaluation",
            "task_provider_requests": count("provider_request_ready"),
            "task_provider_attempts": count("provider_request_attempt"),
            "task_tool_calls_proposed": proposed,
            "task_usage": usage,
            "pma_phase_requests": len(pma),
            "pma_phase_statuses": {status: sum(x.get("status") == status for x in pma)
                                   for status in sorted({x.get("status") for x in pma})},
        })
    return record


def main() -> None:
    if DEST.exists():
        raise FileExistsError(DEST)
    private = secrets()
    sources = selected()
    for path in sources:
        if path.suffix == ".tar":
            validate_product(path, private)
    DEST.mkdir(parents=True)
    index = {}
    for source in sources:
        relative = source.relative_to(SOURCE)
        original = source.read_bytes()
        payload = original if source.suffix == ".tar" else sanitize(original, private)
        target = DEST / "raw" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        index[relative.as_posix()] = {
            "source_bytes": len(original), "source_sha256": sha(original),
            "archived_bytes": len(payload), "archived_sha256": sha(payload),
            "redacted": payload != original}
    (DEST / "RAW_TRACE_INDEX.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    mechanical = summary()
    (DEST / "MECHANICAL_SUMMARY.json").write_text(json.dumps(mechanical, indent=2),
                                                   encoding="utf-8")
    sections = ["PMA/GA retry batch, engineering evidence only.",
                "The first compatibility round failed Task HTTP 403; the new independent "
                "round succeeded (Task 1/1, PMA 2/2). The service-side cause of the earlier "
                "403 remains unknown. No arm was retried or replaced.",
                "A arms wrote CURRENT_TASK_DONE to job task_terminal.json but the frozen "
                "host hook recorded task_terminal=null. The A record also contains "
                "pma_finalization=not_enabled; its shape differs from the Task-only hook "
                "contract, so native evaluation was withheld. Do not interpret Harbor's "
                "aggregate 0 as a native reward for these arms.",
                "B arms passed the terminal/freeze gate and were each evaluated once; both "
                "native reward.txt files contain 0. PMA lifecycle and task correctness are "
                "distinct. No effectiveness claim is made.",
                "Original raw source remains at the named external batch root. This export "
                "includes compatibility, archives, job records, B worker records and protocol "
                "spool; it excludes staged bundles, GA source mirrors, caches, and unrelated "
                "host files. Task provider capture supplies event hashes/usage and console "
                "logs, not complete raw wire request bodies. Redactions are indexed.",
                "===== MECHANICAL_SUMMARY.json =====", json.dumps(mechanical, indent=2),
                "===== RAW_TRACE_INDEX.json =====", json.dumps(index, indent=2)]
    for relative in sorted(index):
        if relative.endswith(".tar"):
            continue
        path = DEST / "raw" / relative
        sections += ["===== " + relative + " =====", path.read_text(encoding="utf-8")]
    (DEST / "AUDIT_PACKET.txt").write_text("\n\n".join(sections), encoding="utf-8")
    zip_path = DEST / "RAW_TRAJECTORIES.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in sorted(index):
            archive.write(DEST / "raw" / relative, relative)
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")
        for relative, entry in index.items():
            payload = archive.read(relative)
            if len(payload) != entry["archived_bytes"] or sha(payload) != entry["archived_sha256"]:
                raise RuntimeError(f"ZIP identity mismatch: {relative}")


if __name__ == "__main__":
    main()
