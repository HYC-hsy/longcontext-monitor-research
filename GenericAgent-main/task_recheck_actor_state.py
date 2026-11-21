"""Default-off, private pre-request state capture for Task continuation checks."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

CONFIG_FIELDS = ('model', 'temperature', 'max_tokens', 'thinking_type',
                 'reasoning_effort', 'stream', 'max_retries', 'read_timeout',
                 'api_mode', 'context_win', 'fake_cc_system_prompt')
ENV_FIELDS = ('GA_LLM_CONFIG_NAME', 'GA_LANG', 'GA_TASK_COMPLETE_RESPONSE',
              'GA_PROVIDER_MAX_RETRIES', 'GA_TASK_DEADLINE_EPOCH',
              'GA_EXPERIMENT_RUNTIME_POLICY', 'GA_RUN_ISOLATION')


def capture_pre_request(*, turn, client, messages, pre_reminder_messages,
                        reminder, tools_schema, handler, initial_task,
                        directory: Path = Path('/logs/agent')):
    if os.environ.get("GA_TASK_RECHECK_CAPTURE") != "1" or turn <= 1:
        return None
    run_id = os.environ.get("GA_BENCH_RUN_ID")
    directory = Path(directory)
    if not run_id or not directory.is_dir():
        raise RuntimeError("Task recheck capture needs bound run and private agent log mount")
    backend = client.backend
    import llmcore
    profile_path = getattr(llmcore, '_mykey_path', None)
    profile_hash = (hashlib.sha256(Path(profile_path).read_bytes()).hexdigest()
                    if profile_path and Path(profile_path).is_file() else None)
    row = {
        "schema": "task-recheck-actor-state-v1", "run_id": run_id,
        "task_id": os.environ.get("GA_BENCH_TASK_ID"), "actor_attempt": turn,
        "initial_task": initial_task,
        "captured_at_epoch": time.time(),
        "messages": copy.deepcopy(messages),
        "pre_reminder_messages": copy.deepcopy(pre_reminder_messages),
        "pending_reminder": reminder,
        "tools_schema": copy.deepcopy(tools_schema),
        "backend_history": copy.deepcopy(backend.history),
        "backend_system": getattr(backend, "system", ""),
        "effective_model_config": {field: getattr(backend, field, None)
                                   for field in CONFIG_FIELDS},
        "api_base_sha256": hashlib.sha256(
            str(getattr(backend, 'api_base', '')).encode('utf-8')).hexdigest(),
        "task_environment": {name: os.environ.get(name) for name in ENV_FIELDS},
        "task_profile_path": profile_path,
        "task_profile_sha256": profile_hash,
        "pending_tool_ids": list(getattr(client, "_pending_tool_ids", [])),
        "last_tools": getattr(client, "last_tools", ""),
        "total_cd_tokens": getattr(client, "total_cd_tokens", 0),
        "role": getattr(client, "role", None),
        "session_ids": {name: getattr(backend, name, None) for name in
                        ("_session_id", "_account_uuid", "_device_id")},
        "handler_working": copy.deepcopy(getattr(handler, "working", {})),
        "handler_history_info": copy.deepcopy(getattr(handler, "history_info", [])),
    }
    encoded = (json.dumps(row, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode("utf-8")
    path = directory / f"task_recheck_before_actor_{turn:04d}.json"
    if path.exists() or path.is_symlink():
        raise RuntimeError("Task recheck pre-request state already exists")
    fd, pending = tempfile.mkstemp(prefix=".task-recheck-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        if os.path.exists(pending):
            os.unlink(pending)
    return {"path": str(path), "bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest()}
