"""Build a visible-only public projection of the stopped model4 batch."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(r"E:\LongContext\_pma_model4_claude_first20_98b_20261109")
OUT = ROOT / "MODEL4_CLAUDE_FIRST_PARTIAL_20261109.zip"
INDEX = ROOT / "MODEL4_CLAUDE_FIRST_PARTIAL_20261109.index.json"
DROP_KEYS = {
    "signature", "thinking_content", "reasoning_content", "api_key",
    "authorization", "proxy_authorization", "experimental_bearer_token",
    "password", "secret", "private_key", "access_token", "refresh_token",
}
ENDPOINT_KEYS = {"provider_url", "base_url", "endpoint", "model_catalog_url"}
PRIVATE_BLOCK_TYPES = {"thinking", "redacted_thinking", "reasoning"}
SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_-]{12,}"), "[REDACTED_KEY]"),
    (re.compile(r"(?i)Bearer\s+[A-Za-z0-9._-]{12,}"), "Bearer [REDACTED]"),
    (re.compile(r"https?://cc-vibe\.com[^\s\"']*", re.I), "[REDACTED_ENDPOINT]"),
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_string(value: str) -> str:
    for pattern, replacement in SECRET_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def project(value):
    if isinstance(value, dict):
        if str(value.get("type", "")).lower() in PRIVATE_BLOCK_TYPES:
            return {"type": "[PRIVATE_BLOCK_EXCLUDED]"}
        result = {}
        for key, item in value.items():
            lower = str(key).lower()
            if lower in DROP_KEYS or "signature" in lower:
                result[key] = "[EXCLUDED_PRIVATE_FIELD]"
            elif lower in ENDPOINT_KEYS:
                result[key] = "[REDACTED_ENDPOINT]"
            elif lower in {"headers", "http_headers"} and isinstance(item, dict):
                result[key] = {
                    k: ("[REDACTED_AUTH_HEADER]" if "auth" in k.lower() or "key" in k.lower() else project(v))
                    for k, v in item.items()
                }
            else:
                result[key] = project(item)
        return result
    if isinstance(value, list):
        return [project(item) for item in value]
    if isinstance(value, str):
        return clean_string(value)
    return value


def projection(path: Path) -> bytes:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".jsonl":
        lines = [json.dumps(project(json.loads(line)), ensure_ascii=False, separators=(",", ":")) for line in raw.splitlines() if line]
        return ("\n".join(lines) + "\n").encode("utf-8")
    if path.suffix == ".json":
        return (json.dumps(project(json.loads(raw)), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return clean_string(raw).encode("utf-8")


def selected_files():
    for name in ("batch.stdout.log", "batch.stderr.log", "run_all.ps1"):
        path = ROOT / name
        if path.is_file():
            yield path
    for slot in sorted((ROOT / "runs").iterdir()):
        if not slot.is_dir():
            continue
        for name in ("run_claim.json", "selection_result.json", "experiment_plan.json"):
            path = slot / name
            if path.is_file():
                yield path
        for path in slot.glob("*/batch_result.json"):
            yield path
        for path in slot.glob("*/runs/*/archive/*"):
            if path.is_file() and path.suffix in {".json", ".log", ".txt"}:
                yield path
        for path in slot.glob("*/runs/*/host_private/archive/*"):
            if path.is_file() and path.name in {
                "accepted.jsonl", "events.jsonl", "memory.json",
                "memory_payload.jsonl", "memory_response.jsonl",
                "memory_transport.jsonl", "trajectory_memory.json",
            }:
                yield path
        for path in slot.glob("*/runs/*/jobs/*/public_task*/agent/*"):
            if path.is_file() and path.name in {
                "agent_process_return_code.txt", "agent_stderr.log", "agent_stdout.log",
                "m4_agent_identity.json", "otel_trace.json", "output.txt",
                "research_events.jsonl", "task_terminal.json",
            }:
                yield path


def main():
    if OUT.exists() or INDEX.exists():
        raise RuntimeError("archive already exists; never overwrite")
    records = []
    files = list(dict.fromkeys(selected_files()))
    if len(list((ROOT / "runs").iterdir())) != 17 or len(files) < 250:
        raise RuntimeError("unexpected slot/file count")
    with zipfile.ZipFile(OUT, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            original = path.read_bytes()
            public = projection(path)
            member = path.relative_to(ROOT).as_posix()
            archive.writestr(member, public)
            records.append({
                "path": member,
                "source_sha256": sha(original),
                "source_bytes": len(original),
                "public_sha256": sha(public),
                "public_bytes": len(public),
                "projection": "parsed-json-field-filter" if path.suffix in {".json", ".jsonl"} else "text-secret-pattern-filter",
            })
        note = (
            "Public visible projection, not raw HTTP bytes. Source originals remain on the local machine. "
            "Private thinking/signatures, credentials, authorization headers, private endpoints, "
            "full profiles, hidden verifier content, execution source bundles, and unrelated task files are excluded. "
            "17 attempted slots: 16 native evaluations and one GPT P1 engineering failure; three GPT slots unstarted.\n"
        ).encode("utf-8")
        archive.writestr("PUBLIC_PROJECTION_NOTICE.txt", note)
        records.append({"path": "PUBLIC_PROJECTION_NOTICE.txt", "source_sha256": None, "source_bytes": None,
                        "public_sha256": sha(note), "public_bytes": len(note), "projection": "generated_notice"})
    with zipfile.ZipFile(OUT) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC failed: {bad}")
        for record in records:
            if sha(archive.read(record["path"])) != record["public_sha256"]:
                raise RuntimeError(f"member hash failed: {record['path']}")
    result = {
        "schema": "model4-public-visible-partial-index-v1",
        "execution_sha": "98b166aa747da9f5b7e9f0f9d677c25d77d3611a",
        "dataset_sha": "2fd12b88aafdd04a52c298e3940bcb189f9766d6",
        "harbor_sha": "459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc",
        "zip": OUT.name,
        "zip_bytes": OUT.stat().st_size,
        "zip_sha256": sha(OUT.read_bytes()),
        "files": records,
        "missing": ["GPT slots 10, 13, 20 not started", "slot 07 native evaluation not executed"],
    }
    INDEX.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"zip_bytes": result["zip_bytes"], "zip_sha256": result["zip_sha256"],
                      "file_count": len(records), "zip_crc": "ok"}))


if __name__ == "__main__":
    main()
