"""Restore a frozen Task pre-request state for isolated short continuations.

The public branch text is a replacement for only the current pending PMA
reminder. Prior Task history, including reminders already delivered, is kept.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from pma_upstream_bridge import append_reminder
from task_recheck_actor_state import CONFIG_FIELDS


FIXED_TEXT = (
    "Before continuing, review the original task alongside the current "
    "artifacts and execution results, and check what still needs to be done."
)
TARGETED_TEXT = (
    "Before continuing, compare a few extracted amounts with the "
    "corresponding source documents or OCR text."
)
BRANCH_TEXT = {"none": None, "fixed": FIXED_TEXT, "targeted": TARGETED_TEXT}


def load_frozen(path: str | Path) -> dict:
    row = json.loads(Path(path).read_text(encoding="utf-8"))
    if row.get("schema") != "task-recheck-actor-state-v1":
        raise ValueError("wrong Task checkpoint schema")
    if not isinstance(row.get("actor_attempt"), int) or row["actor_attempt"] <= 1:
        raise ValueError("checkpoint is not a post-tool Task boundary")
    if not isinstance(row.get("backend_history"), list):
        raise ValueError("checkpoint lacks native Task history")
    if not isinstance(row.get("pre_reminder_messages"), list):
        raise ValueError("checkpoint lacks pre-reminder messages")
    if not isinstance(row.get("tools_schema"), list):
        raise ValueError("checkpoint lacks Task tool definitions")
    expected = copy.deepcopy(row["pre_reminder_messages"])
    if row.get("pending_reminder"):
        expected[-1] = append_reminder(expected[-1], row["pending_reminder"])
    if expected != row.get("messages"):
        raise ValueError("checkpoint reminder assembly does not match original Task input")
    return row


def branch_messages(row: dict, arm: str) -> list[dict]:
    if arm not in BRANCH_TEXT:
        raise ValueError("unknown frozen branch arm")
    messages = copy.deepcopy(row["pre_reminder_messages"])
    if BRANCH_TEXT[arm] is not None:
        messages[-1] = append_reminder(messages[-1], BRANCH_TEXT[arm])
    return messages


def restore_native_state(row: dict, client, handler) -> None:
    backend = client.backend
    import hashlib
    from pathlib import Path
    profile_path = row.get('task_profile_path')
    profile_hash = row.get('task_profile_sha256')
    if profile_path and profile_hash:
        if (not Path(profile_path).is_file() or
                hashlib.sha256(Path(profile_path).read_bytes()).hexdigest() != profile_hash):
            raise RuntimeError('Task branch private profile bytes differ from checkpoint')
    actual = {field: getattr(backend, field, None) for field in CONFIG_FIELDS}
    if actual != row['effective_model_config']:
        raise RuntimeError('Task branch model configuration differs from frozen request')
    if (hashlib.sha256(str(getattr(backend, 'api_base', '')).encode('utf-8')).hexdigest()
            != row['api_base_sha256']):
        raise RuntimeError('Task branch provider route differs from frozen request')
    backend.history = copy.deepcopy(row["backend_history"])
    backend.system = row["backend_system"]
    client._pending_tool_ids = list(row["pending_tool_ids"])
    client.last_tools = row["last_tools"]
    client.total_cd_tokens = row["total_cd_tokens"]
    client.role = row["role"]
    for name, value in row["session_ids"].items():
        if value is not None:
            setattr(backend, name, value)
    handler.working = copy.deepcopy(row["handler_working"])
    handler.history_info = copy.deepcopy(row["handler_history_info"])
