"""Apply the LHTB structured pass-signal compatibility patch."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "harbor_0_20_lhtb_structured_pass.patch"
DEFAULT_HARBOR_ROOT = Path(r"E:\LongContext\bench_runtime\m4\harbor-src")
EXPECTED_HARBOR_COMMIT = "459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc"
EXPECTED_PATCH_SHA256 = (
    "461fde1bb2a832be571ecfa1d0ca6ad46022a5ea8fbda5668033dad76a4aff87"
)
PATCHED_PATH = "src/harbor/trial/single_step.py"
LEGACY_STDOUT_BLOCK = """        if result.return_code or not result.stdout.strip():
            return False
        try:
            payload = json.loads(result.stdout)
"""
CURRENT_STDOUT_BLOCK = """        stdout = result.stdout or ""
        if result.return_code or not stdout.strip():
            return False
        try:
            payload = json.loads(stdout)
"""


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.resolve().as_posix()}",
            "-C",
            str(root),
            *args,
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def validate(root: Path) -> None:
    if hashlib.sha256(PATCH.read_bytes()).hexdigest() != EXPECTED_PATCH_SHA256:
        raise RuntimeError("structured pass patch hash mismatch")
    head = git(root, "rev-parse", "HEAD")
    if head.returncode or head.stdout.strip() != EXPECTED_HARBOR_COMMIT:
        raise RuntimeError("Harbor source commit mismatch")


def state(root: Path) -> str:
    if git(root, "apply", "--recount", "--check", str(PATCH)).returncode == 0:
        return "unapplied"
    if (
        git(root, "apply", "--recount", "--reverse", "--check", str(PATCH)).returncode
        == 0
    ):
        return "applied"
    source = (root / PATCHED_PATH).read_text(encoding="utf-8")
    if LEGACY_STDOUT_BLOCK in source:
        return "legacy-applied"
    raise RuntimeError(
        "structured pass patch requires the pinned continuation patch first"
    )


def apply(root: Path) -> str:
    validate(root)
    current = state(root)
    if current == "applied":
        return current
    if current == "legacy-applied":
        target = root / PATCHED_PATH
        source = target.read_text(encoding="utf-8")
        if source.count(LEGACY_STDOUT_BLOCK) != 1:
            raise RuntimeError("legacy structured stdout block is ambiguous")
        target.write_text(
            source.replace(LEGACY_STDOUT_BLOCK, CURRENT_STDOUT_BLOCK),
            encoding="utf-8",
        )
        return state(root)
    result = git(root, "apply", "--recount", str(PATCH))
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return state(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harbor-root", type=Path, default=DEFAULT_HARBOR_ROOT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    validate(args.harbor_root)
    current = apply(args.harbor_root) if args.apply else state(args.harbor_root)
    print(
        f"harbor_commit={EXPECTED_HARBOR_COMMIT} "
        f"patch_sha256={EXPECTED_PATCH_SHA256} state={current}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
