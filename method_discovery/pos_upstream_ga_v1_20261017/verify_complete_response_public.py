"""Read back the public stopped-run archive and screen private profile values."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from .collect_native_shared import secrets_from_profile


def check_structured(value) -> None:
    if isinstance(value, dict):
        if "user_id" in value and value["user_id"] != "[REDACTED_PROVIDER_USER_ID]":
            raise RuntimeError("provider user identity in public member")
        if "provider_url" in value and value["provider_url"] != "[REDACTED]":
            raise RuntimeError("provider endpoint in public member")
        for key, item in value.items():
            if key in {"redacted_thinking", "reasoning_content", "encrypted_content",
                       "signature", "thinking_signature"} and not (
                       isinstance(item, dict) and item.get("public_projection") ==
                       "[REDACTED_HIDDEN_THINKING]"):
                raise RuntimeError("hidden provider content in public member")
            if key == "thinking" and not (
                    isinstance(item, dict) and (
                        item.get("public_projection") == "[REDACTED_HIDDEN_THINKING]" or
                        set(item) <= {"type", "budget_tokens"} and
                        item.get("type") in {"adaptive", "enabled", "disabled"})):
                raise RuntimeError("hidden thinking in public member")
            check_structured(item)
    elif isinstance(value, list):
        for item in value:
            check_structured(item)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--task-profile", required=True, type=Path)
    parser.add_argument("--git-ref")
    args = parser.parse_args()
    root = args.archive.resolve(strict=True)
    index = json.loads((root / "FILE_HASHES.json").read_text(encoding="utf-8"))
    secrets = [value.encode() for value in secrets_from_profile(args.task_profile)]
    checked = 0
    checkout = Path(__file__).resolve().parents[2]
    for row in index["files"]:
        for part in row["public_parts"]:
            path = (root / part["path"]).resolve(strict=True)
            if not path.is_relative_to(root):
                raise RuntimeError("public member outside archive")
            data = path.read_bytes()
            if (len(data) != part["bytes"] or
                    hashlib.sha256(data).hexdigest() != part["sha256"]):
                raise RuntimeError("public readback mismatch")
            if args.git_ref:
                relative = path.relative_to(checkout).as_posix()
                committed = subprocess.run(["git", "show", args.git_ref + ":" + relative],
                                           cwd=checkout, check=True, capture_output=True).stdout
                if committed != data:
                    raise RuntimeError("Git blob/public byte mismatch")
            if any(secret in data for secret in secrets):
                raise RuntimeError("private profile value in public member")
            if re.search(rb"(?i)authorization\s*[:=]\s*bearer\s+(?!\[REDACTED\])[^\s\"']+", data):
                raise RuntimeError("unredacted bearer token in public member")
            if row["path"] == "01/pos/events.provider.jsonl":
                for line in data.splitlines():
                    check_structured(json.loads(line))
            checked += 1
    print(json.dumps({"status": "pass", "public_members_checked": checked,
                      "private_profile_values_found": 0,
                      "index_sha256": hashlib.sha256((root / "FILE_HASHES.json").read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
