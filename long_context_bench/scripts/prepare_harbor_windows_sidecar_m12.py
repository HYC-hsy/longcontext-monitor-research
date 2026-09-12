"""Apply the pinned Harbor Windows-to-Linux sidecar line-ending fix."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "harbor_0_20_windows_sidecar_crlf.patch"
DEFAULT_HARBOR_ROOT = Path(r"E:\LongContext\bench_runtime\m4\harbor-src")
EXPECTED_HARBOR_COMMIT = "459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc"
EXPECTED_PATCH_SHA256 = (
    "5a33173d973b0afed9d258b033137398647438e6c89cb7e2efc47ad31ec445e0"
)
PATCHED_PATH = (
    "src/harbor/environments/docker/"
    "harbor-docker-egress-control-sidecar/Dockerfile"
)


def git(harbor_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={harbor_root.resolve().as_posix()}",
            "-C",
            str(harbor_root),
            *args,
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def validate(harbor_root: Path) -> None:
    digest = hashlib.sha256(PATCH.read_bytes()).hexdigest()
    if digest != EXPECTED_PATCH_SHA256:
        raise RuntimeError(f"sidecar patch hash mismatch: {digest}")
    commit = git(harbor_root, "rev-parse", "HEAD")
    if commit.returncode or commit.stdout.strip() != EXPECTED_HARBOR_COMMIT:
        raise RuntimeError("Harbor source commit mismatch")


def state(harbor_root: Path) -> str:
    if git(harbor_root, "apply", "--check", str(PATCH)).returncode == 0:
        return "unapplied"
    if (
        git(harbor_root, "apply", "--reverse", "--check", str(PATCH)).returncode
        == 0
    ):
        return "applied"
    raise RuntimeError("sidecar patch cannot be cleanly applied or reversed")


def apply(harbor_root: Path) -> str:
    validate(harbor_root)
    current = state(harbor_root)
    if current == "applied":
        return current
    dirty = git(harbor_root, "diff", "--quiet", "--", PATCHED_PATH)
    if dirty.returncode:
        raise RuntimeError("refusing to overwrite a modified sidecar Dockerfile")
    result = git(harbor_root, "apply", str(PATCH))
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return state(harbor_root)


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
