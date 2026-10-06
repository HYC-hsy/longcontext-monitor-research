"""Zero-model, byte-exact prompt revision record against the frozen production base."""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess


BASE = "0a34cd63332b66b74cc21f00b6cb35803dd8648b"
PRODUCTION = "GenericAgent-main/monitor_agent_core/ase_v0.py"
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def source_at_base(path: str) -> bytes:
    return git("show", f"{BASE}:{path}")


def prompt_and_literal(source: bytes) -> tuple[str, str]:
    decoded = source.decode("utf-8")
    tree = ast.parse(decoded)
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "SYSTEM_PROMPT"
                           for target in node.targets)]
    if len(assignments) != 1 or not isinstance(assignments[0].value, ast.Constant):
        raise RuntimeError("Expected exactly one literal SYSTEM_PROMPT assignment")
    value = assignments[0].value.value
    if not isinstance(value, str):
        raise RuntimeError("SYSTEM_PROMPT is not text")
    literal = ast.get_source_segment(decoded, assignments[0].value)
    if literal is None:
        raise RuntimeError("Cannot extract prompt literal")
    return value, literal


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def freeze() -> dict:
    before_source = source_at_base(PRODUCTION)
    after_source = (ROOT / PRODUCTION).read_bytes()
    before, before_literal = prompt_and_literal(before_source)
    after, after_literal = prompt_and_literal(after_source)
    before_rest = before_source.replace(before_literal.encode("utf-8"), b"<SYSTEM_PROMPT>", 1)
    after_rest = after_source.replace(after_literal.encode("utf-8"), b"<SYSTEM_PROMPT>", 1)
    if before_rest != after_rest:
        raise RuntimeError("Production source differs outside SYSTEM_PROMPT")
    changed = git("diff", "--name-only", BASE, "--", "GenericAgent-main").decode().splitlines()
    if changed != [PRODUCTION]:
        raise RuntimeError(f"Unexpected production diff: {changed}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "SYSTEM_PROMPT_BEFORE.txt").write_bytes(before.encode("utf-8"))
    (OUT / "SYSTEM_PROMPT_AFTER.txt").write_bytes(after.encode("utf-8"))
    prompt_diff = "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile="SYSTEM_PROMPT_BEFORE", tofile="SYSTEM_PROMPT_AFTER"))
    (OUT / "SYSTEM_PROMPT_DIFF.patch").write_bytes(prompt_diff.encode("utf-8"))
    (OUT / "PRODUCTION_DIFF.patch").write_bytes(
        git("diff", "--binary", BASE, "--", PRODUCTION))
    record = {
        "baseline_production_commit": BASE,
        "production_changed_files": changed,
        "source_equal_after_replacing_only_prompt_literal": True,
        "before_prompt_utf8_bytes": len(before.encode("utf-8")),
        "before_prompt_sha256": sha(before.encode("utf-8")),
        "after_prompt_utf8_bytes": len(after.encode("utf-8")),
        "after_prompt_sha256": sha(after.encode("utf-8")),
        "prompt_file_semantics": "exact Python string value, with no added final LF",
        "prompt_diff_sha256": sha(prompt_diff.encode("utf-8")),
        "production_diff_sha256": sha((OUT / "PRODUCTION_DIFF.patch").read_bytes()),
        "model_provider_calls": 0,
        "task_agent_calls": 0,
    }
    (OUT / "FREEZE.json").write_bytes(
        (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return record


if __name__ == "__main__":
    print(json.dumps(freeze(), ensure_ascii=False))
