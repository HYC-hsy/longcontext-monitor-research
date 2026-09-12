"""Validate or apply the pinned Harbor 0.20 LHTB continuation port."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "harbor_0_20_lhtb_continue.patch"
DEFAULT_HARBOR_ROOT = Path(r"E:\LongContext\bench_runtime\m4\harbor-src")
EXPECTED_HARBOR_COMMIT = "459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc"
EXPECTED_PATCH_SHA256 = (
    "b7a99b6a2e9aa9f879bf5d7753b168811ae37ac34cc81dba6a52c9406bce87b0"
)
PATCHED_PATHS = (
    "src/harbor/models/task/config.py",
    "src/harbor/trial/single_step.py",
)


def run_git(harbor_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
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


def validate_identity(harbor_root: Path) -> None:
    actual_patch_hash = hashlib.sha256(PATCH.read_bytes()).hexdigest()
    if actual_patch_hash != EXPECTED_PATCH_SHA256:
        raise RuntimeError(
            f"continuation patch hash mismatch: {actual_patch_hash}"
        )
    commit = run_git(harbor_root, "rev-parse", "HEAD")
    if commit.returncode or commit.stdout.strip() != EXPECTED_HARBOR_COMMIT:
        raise RuntimeError(
            "Harbor source identity mismatch: expected "
            f"{EXPECTED_HARBOR_COMMIT}, got {commit.stdout.strip() or commit.stderr.strip()}"
        )


def patch_state(harbor_root: Path) -> str:
    forward = run_git(harbor_root, "apply", "--check", str(PATCH))
    if forward.returncode == 0:
        return "unapplied"
    reverse = run_git(harbor_root, "apply", "--reverse", "--check", str(PATCH))
    if reverse.returncode == 0:
        return "applied"
    config_path = harbor_root / PATCHED_PATHS[0]
    trial_path = harbor_root / PATCHED_PATHS[1]
    if config_path.is_file() and trial_path.is_file():
        config_source = config_path.read_text(encoding="utf-8")
        trial_source = trial_path.read_text(encoding="utf-8")
        config_markers = (
            "continue_until_timeout: bool = Field(",
            "same agent session until verification passes",
        )
        trial_markers = (
            "def _merge_agent_contexts(",
            "async def _run_agent_until_verified(",
            '"continue_until_timeout_phases"',
            "await self._run_shared_verifier(",
        )
        if all(marker in config_source for marker in config_markers) and all(
            marker in trial_source for marker in trial_markers
        ):
            # A pinned dependent patch may extend single_step.py, so the original
            # patch is no longer byte-for-byte reversible even though its full
            # continuation contract remains present.
            return "applied"
    raise RuntimeError(
        "Harbor continuation patch is neither cleanly applicable nor cleanly "
        f"reversible:\n{forward.stderr}\n{reverse.stderr}"
    )


def apply_patch(harbor_root: Path) -> str:
    validate_identity(harbor_root)
    state = patch_state(harbor_root)
    if state == "applied":
        return state
    dirty = run_git(harbor_root, "diff", "--quiet", "--", *PATCHED_PATHS)
    if dirty.returncode != 0:
        raise RuntimeError("refusing to patch locally modified Harbor target files")
    applied = run_git(harbor_root, "apply", str(PATCH))
    if applied.returncode:
        raise RuntimeError(applied.stderr or applied.stdout)
    if patch_state(harbor_root) != "applied":
        raise RuntimeError("Harbor patch did not reach the expected applied state")
    return "applied"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--harbor-root", type=Path, default=DEFAULT_HARBOR_ROOT
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the pinned patch; default behavior only validates it.",
    )
    args = parser.parse_args()

    validate_identity(args.harbor_root)
    state = (
        apply_patch(args.harbor_root)
        if args.apply
        else patch_state(args.harbor_root)
    )
    print(
        f"harbor_commit={EXPECTED_HARBOR_COMMIT} "
        f"patch_sha256={EXPECTED_PATCH_SHA256} state={state}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
