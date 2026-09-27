"""Pure synthetic request-difference harness; never contacts a provider."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent

M1_SYSTEM = (ROOT / "M1_REFERENCE_CONTRACT.txt").read_text(encoding="utf-8").strip()

TASK = "A public task requires a local implementation change and a later whole-task completion decision."
INITIAL_STATE = "Decision: assess completion. Focal uncertainty: whether the local observation supports the requested scope."
HISTORY = [{"role": "user", "content": "Inspect the public task and available workspace evidence."}]
TOOLS = [
    {"name": "file_read", "arguments": ["path", "start", "count"]},
    {"name": "file_write", "arguments": ["path", "content", "mode"]},
    {"name": "file_patch", "arguments": ["path", "old_text", "new_text"]},
    {"name": "code_run", "arguments": ["code", "type", "session_id", "wait_seconds", "timeout", "cancel"]},
    {"name": "wait", "arguments": ["after_turns", "mode"]},
    {"name": "intervene", "arguments": ["message"]},
    {"name": "allow_complete", "arguments": []},
]


def _overlay(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8").strip()


def build(kind: str) -> dict:
    if kind not in {"M1", "R", "P"}:
        raise ValueError(kind)
    system = M1_SYSTEM
    if kind == "R":
        system += "\n\n" + _overlay("R_POLICY.txt")
    elif kind == "P":
        system += "\n\n" + _overlay("P_POLICY.txt")
    # The condition is deliberately not put in any model-visible field.
    return {
        "system": system,
        "messages": copy.deepcopy(HISTORY),
        "task": TASK,
        "initial_working_state": INITIAL_STATE,
        "tools": copy.deepcopy(TOOLS),
        "model_parameters": {"temperature": 0, "max_tokens": 1200},
    }


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def diff(base: dict, candidate: dict) -> dict:
    keys = sorted(set(base) | set(candidate))
    changed = [key for key in keys if base.get(key) != candidate.get(key)]
    added = [key for key in keys if key not in base]
    removed = [key for key in keys if key not in candidate]

    def nested(left, right, path=""):
        if isinstance(left, dict) and isinstance(right, dict):
            out = []
            for key in sorted(set(left) | set(right)):
                child = f"{path}.{key}" if path else key
                if key not in left or key not in right:
                    out.append(child)
                elif left[key] != right[key]:
                    out.extend(nested(left[key], right[key], child))
            return out
        if isinstance(left, list) and isinstance(right, list):
            return [path] if left != right else []
        return [path] if left != right else []

    return {
        "changed_top_level_keys": changed,
        "added_top_level_keys": added,
        "removed_top_level_keys": removed,
        "changed_paths": nested(base, candidate),
        "common_hashes": {
            key: digest(base[key]) for key in keys
            if key in base and key in candidate and base[key] == candidate[key]
        },
        "system_suffix_only": (
            candidate["system"].startswith(base["system"] + "\n\n")
            and base["messages"] == candidate["messages"]
        ),
    }


def assert_invariants() -> dict:
    m1, r, p = build("M1"), build("R"), build("P")
    for candidate in (r, p):
        assert candidate["messages"] == m1["messages"]
        assert candidate["task"] == m1["task"]
        assert candidate["initial_working_state"] == m1["initial_working_state"]
        assert candidate["tools"] == m1["tools"]
        assert candidate["model_parameters"] == m1["model_parameters"]
    assert "FREE" not in r["system"] and "PROTOCOL" not in r["system"]
    assert "D1" not in r["system"] and "verifier" not in r["system"].lower()
    assert "FREE" not in p["system"] and "PROTOCOL" not in p["system"]
    assert diff(m1, r)["changed_top_level_keys"] == ["system"]
    assert diff(m1, p)["changed_top_level_keys"] == ["system"]
    assert diff(m1, r)["changed_paths"] == ["system"]
    assert diff(m1, p)["changed_paths"] == ["system"]
    assert r["system"].endswith(_overlay("R_POLICY.txt"))
    assert p["system"].endswith(_overlay("P_POLICY.txt"))
    # Deliberate mutation checks prove the audit is not a top-level smoke test.
    extra = copy.deepcopy(m1)
    extra["research_metadata"] = {"condition": "R"}
    assert "research_metadata" in diff(m1, extra)["added_top_level_keys"]
    removed_tool = copy.deepcopy(m1)
    removed_tool["tools"] = removed_tool["tools"][:-1]
    assert "tools" in diff(m1, removed_tool)["changed_paths"]
    changed_state = copy.deepcopy(m1)
    changed_state["initial_working_state"] += " altered"
    assert "initial_working_state" in diff(m1, changed_state)["changed_paths"]
    return {"M1_vs_R": diff(m1, r), "M1_vs_P": diff(m1, p),
            "adversarial_checks": "PASS"}


if __name__ == "__main__":
    report = assert_invariants()
    print(json.dumps(report, indent=2, ensure_ascii=False))
