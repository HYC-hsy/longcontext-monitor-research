"""Index and read back every official-blob posthoc record without text conversion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent / "posthoc_official_20261014"
OUTPUT = ROOT / "FILE_HASHES.json"


def main() -> None:
    rows = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == OUTPUT:
            continue
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        rows.append({"path": path.relative_to(ROOT).as_posix(),
                     "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
    OUTPUT.write_text(json.dumps({"schema": "official-posthoc-file-hashes-v1",
                                  "files": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    if json.loads(OUTPUT.read_text(encoding="utf-8"))["files"] != rows:
        raise RuntimeError("index readback differs")
    print(f"indexed and read back {len(rows)} files")


if __name__ == "__main__":
    main()
