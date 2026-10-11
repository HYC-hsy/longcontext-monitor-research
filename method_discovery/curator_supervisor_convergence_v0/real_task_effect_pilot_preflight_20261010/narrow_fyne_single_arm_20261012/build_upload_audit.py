"""Build a single uploadable TXT from the archived text evidence, without model calls."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys

from .archive_run import HERE, check_public, secret_markers, sha


def main() -> None:
    manifest = json.loads((HERE / "RAW_FILE_MANIFEST.json").read_text(encoding="utf-8"))
    rows = manifest["copied"]
    sources = [
        HERE / "RUN_ARCHIVE_REPORT.md",
        HERE / "PRELAUNCH_ZERO_MODEL_AUDIT.txt",
        HERE / "RAW_TRACE_INDEX.json",
        HERE / "RAW_FILE_MANIFEST.json",
    ]
    sources.extend(HERE / row["path"] for row in rows if not row["path"].endswith(".gz"))
    unique = list(dict.fromkeys(sources))
    target = HERE / "NARROW_FYNE_SINGLE_ARM_AUDIT.txt"
    if target.exists() and "--rebuild" not in sys.argv[1:]:
        raise FileExistsError(target)
    with target.open("wb") as output:
        output.write(b"NARROW FYNE SINGLE-ARM AUDIT PACKAGE\n")
        output.write(b"Text evidence is sectioned below. Binary frozen tar and ZIP are separate files.\n")
        output.write(f"text_sections={len(unique)}\n".encode("ascii"))
        for source in unique:
            raw = source.read_bytes()
            label = source.relative_to(HERE).as_posix()
            if hashlib.sha256(raw).hexdigest() != sha(source):
                raise RuntimeError("Source changed during audit compilation: " + label)
            try:
                decoded = raw.decode("utf-8")
                encoding = "utf-8"
                body = decoded.encode("utf-8")
            except UnicodeDecodeError:
                encoding = "base64-of-exact-bytes"
                body = base64.b64encode(raw)
            output.write((f"\n===== BEGIN FILE: {label} =====\n"
                          f"bytes={len(raw)} sha256={sha(source)} encoding={encoding}\n").encode("utf-8"))
            output.write(body)
            if not body.endswith(b"\n"):
                output.write(b"\n")
            output.write((f"===== END FILE: {label} =====\n").encode("utf-8"))
    check_public(target, secret_markers())
    print(json.dumps({"audit_txt": str(target), "bytes": target.stat().st_size,
                      "sha256": sha(target), "sections": len(unique)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
