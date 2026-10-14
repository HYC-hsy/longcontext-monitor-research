"""Write reproducible SHA-256 index for fixed offline shadow artifacts."""
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AUDIT = ROOT / "source_memory_audit_20261014"
TARGETS = [ROOT / "source_screen_fake_final_20261014",
           ROOT / "source_screen_request_examples_20261014",
           AUDIT / "SHADOW_RAW.tar.gz", AUDIT / "AUDIT.txt",
           AUDIT / "FINAL_TEST_OUTPUT.txt",
           ROOT / "SOURCE_MEMORY_STATIC_SCREEN_DRAFT.json",
           ROOT / "source_memory.py", ROOT / "source_agent.py",
           *sorted(AUDIT.glob("*.patch"))]
rows = []
for target in TARGETS:
    for path in ([target] if target.is_file() else sorted(target.rglob("*"))):
        if path.is_file():
            rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
                        f"{path.relative_to(ROOT).as_posix()}")
(AUDIT / "HASHES.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
print(f"indexed {len(rows)} files")
