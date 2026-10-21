"""Index the scoped, public offline V2 material without rewriting its bytes."""

import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
TARGET = PACKAGE / "evidence" / "core_contract_repair_v2" / "FILE_HASHES_V2.json"


def main():
    if TARGET.exists():
        raise SystemExit("Refusing to overwrite V2 hash index")
    files = [PACKAGE / "AUDIT_CORE_CONTRACT_REPAIR_V2.txt",
        PACKAGE / "ACCEPTANCE_MATRIX_V2.md"]
    files.extend(path for path in sorted(TARGET.parent.iterdir()) if
        path.is_file() and path != TARGET)
    rows = []
    for path in files:
        raw = path.read_bytes()
        rows.append({"path": str(path.relative_to(PACKAGE)).replace("\\", "/"),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    TARGET.write_text(json.dumps({"schema": "offline-core-v2-file-hashes",
        "files": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"indexed_files": len(rows), "target": str(TARGET)}))


if __name__ == "__main__":
    main()
