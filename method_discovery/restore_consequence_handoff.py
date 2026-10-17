"""Restore the plain-text consequence handoff into a new, isolated directory.

This is a byte-preserving data recovery tool, not an experiment runner.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    source_bytes = args.source.read_bytes()
    document = json.loads(source_bytes.decode("utf-8"))
    assert document["format"] == "consequence-plain-text-handoff-v1"
    files = document["files"]
    assert document["file_count"] == len(files) == 37
    assert not args.destination.exists(), "destination must be new"
    destination = args.destination.resolve()
    assert destination != args.source.resolve()

    checked = []
    names = set()
    for entry in files:
        raw = entry["path"]
        path = PurePosixPath(raw)
        parts = path.parts
        assert (raw == path.as_posix() and not path.is_absolute()
                and len(parts) >= 2 and not any(part in ("", ".", "..") for part in parts))
        assert parts[0] in {"consequence_observer_v0", "verified_three_case_bundle"}
        assert not any("\\" in part or ":" in part for part in parts)
        assert raw not in names, f"duplicate path: {raw}"
        names.add(raw)
        payload = entry["utf8_text"].encode("utf-8")
        assert len(payload) == entry["bytes"], f"byte count mismatch: {raw}"
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"], f"hash mismatch: {raw}"
        checked.append((parts, payload, entry["sha256"]))

    destination.mkdir(parents=True, exist_ok=False)
    for parts, payload, expected in checked:
        target = destination.joinpath(*parts)
        assert target.resolve().is_relative_to(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
            stream.write(payload)
        restored = target.read_bytes()
        assert len(restored) == len(payload)
        assert hashlib.sha256(restored).hexdigest() == expected

    print(json.dumps({
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "restored_files": len(checked),
        "destination": str(destination),
        "all_file_hashes_match": True,
    }, indent=2))


if __name__ == "__main__":
    main()
