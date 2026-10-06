"""Deterministic, zero-model checks for the prompt-only Curator revision."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import re
import subprocess

from .freeze import BASE, OUT, PRODUCTION, ROOT, prompt_and_literal, source_at_base


FROZEN = (
    "GenericAgent-main/monitor_agent_core/runtime.py",
    "GenericAgent-main/monitor_agent_core/agent.py",
    "GenericAgent-main/monitor_agent_core/cfs_v0.py",
    "GenericAgent-main/monitor_agent_core/provider.py",
)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def section(source: bytes, name: str) -> bytes:
    text = source.decode("utf-8")
    tree = ast.parse(text)
    nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name]
    assert len(nodes) == 1
    node = nodes[0]
    return "\n".join(text.splitlines()[node.lineno - 1:node.end_lineno]).encode("utf-8")


def test_only_production_prompt_literal_changed():
    before = source_at_base(PRODUCTION)
    after = (ROOT / PRODUCTION).read_bytes()
    _, old_literal = prompt_and_literal(before)
    _, new_literal = prompt_and_literal(after)
    assert before.replace(old_literal.encode(), b"<PROMPT>", 1) == after.replace(
        new_literal.encode(), b"<PROMPT>", 1)
    assert git("diff", "--name-only", BASE, "--", "GenericAgent-main").decode().splitlines() == [PRODUCTION]


def test_control_echo_byte_identical():
    assert section(source_at_base(PRODUCTION), "ControlEcho") == section(
        (ROOT / PRODUCTION).read_bytes(), "ControlEcho")


def test_frozen_production_files_byte_identical():
    for path in FROZEN:
        # Git blobs are the frozen production identity; Windows checkout may
        # materialize their LF bytes as CRLF without a source change.
        assert git("show", f"HEAD:{path}") == source_at_base(path), path
        assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == source_at_base(path), path


def test_seven_tool_schemas_unchanged():
    path = "GenericAgent-main/monitor_agent_core/agent.py"
    assert git("show", f"HEAD:{path}") == source_at_base(path)
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "MONITOR_TOOLS"
                           for target in node.targets)]
    assert len(assignments) == 1
    names = [node.args[0].value for node in assignments[0].value.elts]
    assert names == ["file_read", "file_write", "file_patch", "code_run",
                     "wait", "intervene", "allow_complete"]


def test_frozen_prompt_files_are_exact():
    before, _ = prompt_and_literal(source_at_base(PRODUCTION))
    after, _ = prompt_and_literal((ROOT / PRODUCTION).read_bytes())
    assert (OUT / "SYSTEM_PROMPT_BEFORE.txt").read_bytes() == before.encode()
    assert (OUT / "SYSTEM_PROMPT_AFTER.txt").read_bytes() == after.encode()
    assert before != after


def test_measurement_policy_is_present_without_case_terms():
    prompt, _ = prompt_and_literal((ROOT / PRODUCTION).read_bytes())
    required = (
        "supervise the measurement first",
        "what it directly observes",
        "concrete state violating a still-relevant task contract",
        "Ground alternatives in the authoritative task",
        "exact command, source, assertions, oracle, and exercised behavioral path",
        "The Task Agent owns implementation, debugging, test construction, and experimentation",
        "It owns constructing, correcting, and running tests and experiments",
        "do not demand further testing merely for reassurance",
        "the absence of a remembered defect as proof of completion",
    )
    assert all(phrase in prompt for phrase in required)
    assert not re.search(r"\b(?:Fyne|RAT|FBR|Sphinx)\b", prompt, re.IGNORECASE)


def test_recorded_hashes_match_exact_prompt_values():
    import json
    record = json.loads((OUT / "FREEZE.json").read_text(encoding="utf-8"))
    for condition in ("before", "after"):
        body = (OUT / f"SYSTEM_PROMPT_{condition.upper()}.txt").read_bytes()
        assert hashlib.sha256(body).hexdigest() == record[f"{condition}_prompt_sha256"]
    assert record["production_changed_files"] == [PRODUCTION]
