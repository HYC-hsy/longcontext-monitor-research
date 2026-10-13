"""Mechanically export only offline, secret-free PMA/GA fixture evidence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


STAGE = Path(__file__).resolve().parent
REPO = STAGE.parents[2]
EVIDENCE = STAGE / "offline_evidence_r2"
RUNS = {
    "db_A": Path("E:/pma-ga-offline-db-a-20261013-r2"),
    "db_B": Path("E:/pma-ga-offline-db-b-20261013-r6"),
    "code_B": Path("E:/pma-ga-offline-code-b-20261013-r4"),
    "code_A": Path("E:/pma-ga-offline-code-a-20261013"),
}


def sanitized(raw: bytes) -> bytes:
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"(?i)(authorization|x-api-key)([\"']?\s*[:=]\s*[\"']?)[^\s\"']+",
                  r"\1\2[REDACTED]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}\b", "[REDACTED_KEY]", text)
    text = re.sub(r"https?://[^\s\"']+", "[REDACTED_URL]", text)
    return text.encode("utf-8")


def save_text(name: str, data: bytes) -> None:
    target = STAGE / name
    target.write_bytes(sanitized(data))


def run_tests() -> None:
    commands = [
        (["C:/Users/hsy/AppData/Local/Temp/pma-ga-py312/Scripts/python.exe",
          "-m", "unittest", "-v", "test_episode"], STAGE),
        (["py", "-3.13", "-m", "pytest", "-q",
          "tests/test_pma_upstream_ga_bridge.py",
          "tests/test_research_agent_loop.py"], REPO / "GenericAgent-main"),
    ]
    sections = []
    for command, cwd in commands:
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                timeout=120)
        sections.append("COMMAND " + json.dumps(command) + "\nCWD " + str(cwd) +
                        "\nEXIT " + str(result.returncode) + "\nSTDOUT\n" +
                        result.stdout.decode("utf-8", "replace") + "\nSTDERR\n" +
                        result.stderr.decode("utf-8", "replace"))
    save_text("TEST_RESULTS_R2.txt", "\n\n".join(sections).encode())


def export_runs() -> dict:
    EVIDENCE.mkdir(exist_ok=True)
    summary = {}
    for label, root in RUNS.items():
        target = EVIDENCE / label
        target.mkdir(exist_ok=True)
        paths = [root / "archive" / name for name in (
            "offline_result.json", "actual_container_mounts.json",
            "harbor.stdout.log", "harbor.stderr.log", "worker.stdout.log",
            "worker.stderr.log")]
        paths += sorted((root / "archive" / "fake_provider_requests").glob("*"))
        if (root / "host_private" / "archive").is_dir():
            paths += [root / "host_private" / "archive" / name for name in (
                "accepted.jsonl", "events.jsonl", "memory_transport.jsonl",
                "memory_payload.jsonl",
                "memory.json", "trajectory_memory.json")]
            paths += [root / "host_private" / "worker_exit.json"]
        paths += list((root / "jobs").rglob("task_terminal.json"))
        for source in paths:
            if source.is_file():
                relative = ("fake_provider_requests/" + source.name
                            if source.parent.name == "fake_provider_requests" else source.name)
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(sanitized(source.read_bytes()))
        result = json.loads((target / "offline_result.json").read_text(encoding="utf-8"))
        summary[label] = {key: result.get(key) for key in (
            "image_id", "repo_digests", "harbor_return_code", "worker_return_code",
            "actual_container_count", "worker_private_mounted", "worker_exit_receipt")}
        request = json.loads((target / "fake_provider_requests" / "0001.json").read_text(
            encoding="utf-8"))
        summary[label]["request_sha256"] = hashlib.sha256(json.dumps(
            request["body"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        summary[label]["provider_capture_count"] = len(list((target /
            "fake_provider_requests").glob("*.json")))
    for task in ("db", "code"):
        a = json.loads((EVIDENCE / f"{task}_A" / "fake_provider_requests" /
                        "0001.json").read_text(encoding="utf-8"))["body"]
        b = json.loads((EVIDENCE / f"{task}_B" / "fake_provider_requests" /
                        "0001.json").read_text(encoding="utf-8"))["body"]
        summary[task + "_parity"] = {
            "system_equal": a.get("system") == b.get("system"),
            "tools_equal": a.get("tools") == b.get("tools"),
            "model_equal": a.get("model") == b.get("model"),
            "generation_equal": {key: a.get(key) for key in
                ("max_tokens", "thinking", "temperature", "stream")} ==
                {key: b.get(key) for key in
                ("max_tokens", "thinking", "temperature", "stream")},
            "public_input_prefix_equal": b["messages"][0]["content"][0]["text"].startswith(
                a["messages"][0]["content"][0]["text"]),
            "b_reminder_visible_in_first_request": "Offline PMA reminder." in json.dumps(b),
        }
    (EVIDENCE / "SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def finish_packet() -> None:
    files = [path for path in sorted(EVIDENCE.rglob("*")) if path.is_file()]
    files += [STAGE / name for name in (
        "episode.py", "event_spool.py", "worker_main.py", "offline_launcher.py",
        "audit_export_r2.py", "test_episode.py", "harbor_adapter.py",
        "FOUR_RUN_MANIFEST_PREPARED.json", "REPORT_R2.md", "TEST_RESULTS_R2.txt")]
    files += [REPO / "GenericAgent-main" / name for name in (
        "agentmain.py", "agent_loop.py", "pma_upstream_bridge.py")]
    hashes = {}
    for path in files:
        relative = path.relative_to(REPO).as_posix()
        raw = path.read_bytes()
        entry = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        if path.suffix == ".py" or path.name in (
                "REPORT_R2.md", "FOUR_RUN_MANIFEST_PREPARED.json"):
            blob = subprocess.run(["git", "show", "HEAD:" + relative], cwd=REPO,
                                  capture_output=True, check=True).stdout
            entry["git_blob_sha256"] = hashlib.sha256(blob).hexdigest()
            entry["git_blob_bytes"] = len(blob)
        hashes[relative] = entry
    (STAGE / "FILE_HASHES_R2.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    diff = subprocess.run(["git", "diff", "ccb841ea1bb738246493dff8802e70eb45fa7bb3",
                           "HEAD", "--", "GenericAgent-main/agentmain.py",
                           "method_discovery/curator_supervisor_convergence_v0/"
                           "pma_full_upstream_ga_v1_20261013"], cwd=REPO,
                          capture_output=True, check=True).stdout
    sections = []
    for name in ("REPORT_R2.md", "FOUR_RUN_MANIFEST_PREPARED.json",
                 "TEST_RESULTS_R2.txt", "FILE_HASHES_R2.json"):
        sections.append("===== " + name + " =====\n" +
                        (STAGE / name).read_text(encoding="utf-8"))
    sections.append("===== FULL DIFF FROM ccb841ea =====\n" + diff.decode("utf-8", "replace"))
    for path in files:
        sections.append("===== " + path.relative_to(REPO).as_posix() + " =====\n" +
                        path.read_text(encoding="utf-8", errors="replace"))
    (STAGE / "AUDIT_PACKET_R2.txt").write_text("\n\n".join(sections), encoding="utf-8")


def main() -> None:
    run_tests()
    summary = export_runs()
    if not all(summary[f"{task}_parity"][key] for task in ("db", "code") for key in (
            "system_equal", "tools_equal", "model_equal", "generation_equal",
            "public_input_prefix_equal", "b_reminder_visible_in_first_request")):
        raise RuntimeError("A/B offline first request parity failed")
    finish_packet()


if __name__ == "__main__":
    main()
