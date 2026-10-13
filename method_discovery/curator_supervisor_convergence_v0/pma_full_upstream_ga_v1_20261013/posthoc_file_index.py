"""Mechanical SHA-256/size index of this round's independent posthoc records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent / "posthoc_20261014"
OUTPUT = ROOT / "FILE_HASHES.json"


def main() -> None:
    if not ROOT.is_dir():
        raise FileNotFoundError(ROOT)
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == OUTPUT:
            continue
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        files.append({"path": path.relative_to(ROOT).as_posix(),
                      "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
    OUTPUT.write_text(json.dumps({"schema": "posthoc-file-hashes-v1", "files": files},
                                 indent=2, ensure_ascii=False), encoding="utf-8")
    check = json.loads(OUTPUT.read_text(encoding="utf-8"))
    if check["files"] != files:
        raise RuntimeError("file-index readback mismatch")
    print(f"indexed and read back {len(files)} files")


if __name__ == "__main__":
    main()
