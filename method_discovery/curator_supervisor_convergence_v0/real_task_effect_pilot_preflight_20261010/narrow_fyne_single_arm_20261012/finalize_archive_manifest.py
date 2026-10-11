"""Hash every remote archive file, excluding this manifest and Python caches."""

from __future__ import annotations

import json
import sys

from .archive_run import HERE, sha


def main() -> None:
    target = HERE / "ARCHIVE_FILE_MANIFEST.json"
    if target.exists() and "--rebuild" not in sys.argv[1:]:
        raise FileExistsError(target)
    entries = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == target or "__pycache__" in path.parts:
            continue
        entries.append({"path": path.relative_to(HERE).as_posix(),
                        "bytes": path.stat().st_size, "sha256": sha(path)})
    target.write_text(json.dumps({"schema": "narrow-fyne-archive-files-v1",
                                  "entries": entries}, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    for entry in entries:
        path = HERE / entry["path"]
        if path.stat().st_size != entry["bytes"] or sha(path) != entry["sha256"]:
            raise RuntimeError("Archive identity changed: " + entry["path"])
    print(json.dumps({"file_count": len(entries), "manifest_sha256": sha(target)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
