"""Thin production-loop bootstrap for a *future authorized* causal arm.

This module does not import a provider or execute an Agent at import time.
The child process loads it inside the frozen task image, at /app, after an
authorization-gated parent has staged only that arm's checkpoint inputs.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


WORKSPACE_SHA = "994ed5f372f0ee6fecda6a600dc970ce4c5fbbb1a8c09acfa9ab3748ce323c60"
WORKSPACE_FILES = 2472
GIT_HEAD = "7229e889d49c81a83b0b7e09400837f67f6ddad5"
GIT_INDEX_TREE = "5608e51084fb359ae0241c84acfc29cfa9095674"
BACKEND_SHA = "17ec23f7b7c78eb8274afd9e874d25a857983d62ac4f78db14a7ebff3c90d5e4"
HISTORY_INFO_SHA = "b22518a3c66b6985bd9718d0bf11efbf9933997eade9b49cf822d2648d435cf9"
WORKING_SHA = "bb0590c60c8033c9ba1e11e701cceae0e4429adcccd73d5ee7bbe912fd6c7d64"
PENDING_TOOL_ID = "toolu_3BEOn74rTQ3gRB06PQpCqM"
TASK_IMAGE = "sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1"
SOURCE_FILE_SHA = {
    "llmcore.py": "4e229383a806bca81fc190053482fa2ffd439735df94e53d23a92fb771d92518",
    "agent_loop.py": "1bcd38b9213c6d444d65c46a4612349a90ed9a3a0ed67e61e1acaebff6d9b262",
    "ga.py": "189c2272545b08dc61fd26a645df0ae0d0dbc07f0f62c8b713bb4f9a34bcb05a",
    "mykey.json": "c3462b8d06113b5398ecb7aa6f8d22dd19584f834c3336426457ab0f29069764",
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_sha(value: object) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def workspace_identity(root: Path) -> dict:
    rows = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        if path.is_symlink():
            raise RuntimeError("Workspace symlink unsupported at checkpoint")
        if path.is_file():
            rows.append((relative.as_posix(), digest(path.read_bytes())))
    rows.sort()
    tree = digest("".join(f"{name}\0{sha}\n" for name, sha in rows).encode("utf-8"))
    return {"ordinary_file_count": len(rows), "workspace_sha256": tree}


def git_identity(root: Path) -> dict:
    if not (root / ".git" / "index").is_file():
        raise RuntimeError("Git-backed /app workspace missing")
    def read(*args: str) -> str:
        return subprocess.check_output(["git", "-c", "core.filemode=false", *args], cwd=root, text=True).strip()
    return {"head": read("rev-parse", "HEAD"), "index_tree": read("write-tree")}


def validate_child_checkpoint(workspace: Path, state: dict, source: Path,
                              expected_request: dict) -> dict:
    if workspace.as_posix() != "/app" or os.environ.get("GA_LANG") != "en":
        raise RuntimeError("Task execution must use /app with GA_LANG=en")
    ws = workspace_identity(workspace)
    git = git_identity(workspace)
    if (ws != {"ordinary_file_count": WORKSPACE_FILES, "workspace_sha256": WORKSPACE_SHA}
            or git != {"head": GIT_HEAD, "index_tree": GIT_INDEX_TREE}):
        raise RuntimeError("Child workspace/Git checkpoint identity mismatch")
    source_sha = {name: digest((source / name).read_bytes()) for name in SOURCE_FILE_SHA}
    if source_sha != SOURCE_FILE_SHA:
        raise RuntimeError("Deployed production source/profile identity mismatch")
    if (canonical_sha(state["backend_history"]) != BACKEND_SHA
            or canonical_sha(state["history_info"]) != HISTORY_INFO_SHA
            or canonical_sha(state["handler_working_state"]) != WORKING_SHA
            or state["handler_current_turn"] != 30
            or state["next_task_turn"] != 31
            or state["native_tool_client_pending_tool_ids"] != [PENDING_TOOL_ID]
            or state["history_compression_call_count"] != 30
            or state["task_prompt_language"] != "en"
            or state["profile_name"] != "native_claude_cc_vibe_opus48"
            or state["profile_public_semantics"]["model"] != "claude-opus-4-8"
            or expected_request["model"] != "claude-opus-4-8"
            or state["system"] != expected_request["system"]
            or state["tools"] != expected_request["tools"]
            or state["provider_metadata_identity"] != json.loads(expected_request["metadata"]["user_id"])
            or state["turn30_tool_result"]["tool_use_id"] != PENDING_TOOL_ID):
        raise RuntimeError("Child runtime/provider identity mismatch")
    return {"workspace": ws, "git": git, "source_file_sha256": source_sha,
            "backend_history_sha256": BACKEND_SHA, "history_info_sha256": HISTORY_INFO_SHA,
            "working_sha256": WORKING_SHA, "compression_counter": 30,
            "pending_tool_id": PENDING_TOOL_ID, "task_image": TASK_IMAGE}


class ProductionBootstrapClient:
    """One historical tool-result call, then exact NativeToolClient pass-through."""

    def __init__(self, underlying, *, system_prompt: str, initial_user_input: str,
                 next_prompt: str, turn30_tool_result: dict, tools: list,
                 capture=None):
        self.underlying = underlying
        self.system_prompt = system_prompt
        self.initial_user_input = initial_user_input
        self.next_prompt = next_prompt
        self.turn30_tool_result = copy.deepcopy(turn30_tool_result)
        self.tools = copy.deepcopy(tools)
        self.capture = capture
        self.bootstrap_calls = 0
        self.pass_through_calls = 0
        self.accepted_responses = 0

    def __getattr__(self, name):
        return getattr(self.underlying, name)

    def chat(self, messages, tools=None):
        if self.bootstrap_calls == 0:
            if (messages != [{"role": "system", "content": self.system_prompt},
                             {"role": "user", "content": self.initial_user_input}]
                    or tools != self.tools):
                raise RuntimeError("Production loop initial call differs from frozen bootstrap")
            self.bootstrap_calls = 1
            historical = [{"role": "system", "content": self.system_prompt},
                          {"role": "user", "content": self.next_prompt,
                           "tool_results": [copy.deepcopy(self.turn30_tool_result)]}]
            if self.capture:
                self.capture("production_chat_input", {"messages": historical, "tools": tools})
            response = yield from self.underlying.chat(historical, tools=tools)
            if response is not None and not (getattr(response, "content", "") or "").startswith("!!!Error:"):
                self.accepted_responses += 1
            if self.capture:
                self.capture("production_chat_result", response_snapshot(response))
            return response
        self.pass_through_calls += 1
        if self.capture:
            self.capture("production_chat_input", {"messages": messages, "tools": tools})
        response = yield from self.underlying.chat(messages, tools=tools)
        if response is not None and not (getattr(response, "content", "") or "").startswith("!!!Error:"):
            self.accepted_responses += 1
        if self.capture:
            self.capture("production_chat_result", response_snapshot(response))
        return response


def response_snapshot(response) -> dict:
    if response is None:
        return {"response": None}
    return {"content": getattr(response, "content", None),
            "raw": getattr(response, "raw", None),
            "tool_calls": [{"id": call.id, "name": call.function.name,
                            "arguments": call.function.arguments}
                           for call in getattr(response, "tool_calls", ())],
            "usage": getattr(response, "usage", None)}


class FirstSendGuard:
    """Compare at the production transport entry, then send that same object."""

    def __init__(self, expected: dict, original_transport, capture):
        self.expected = expected
        self.original_transport = original_transport
        self.capture = capture
        self.sends = 0
        self.first_canonical_sha = None
        self.mismatch = False

    def __call__(self, session, url, headers, payload, parse_fn):
        if self.sends == 0:
            self.first_canonical_sha = canonical_sha(payload)
            if payload != self.expected:
                self.mismatch = True
                raise RuntimeError("First provider payload mismatch before network send")
        self.capture("provider_pre_send", {"body": payload, "canonical_sha256": canonical_sha(payload)})
        self.sends += 1
        return (yield from self.original_transport(session, url, headers, payload, parse_fn))


def restore_production_objects(source: Path, state: dict, *, cwd: Path,
                               task_dir: Path, original_task: str, capture=None):
    """Construct the deployed handler/client without changing production logic."""
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    import agent_loop  # deployed modules, imported only after source gate
    import ga
    import llmcore
    if agent_loop.agent_runner_loop.__module__ != "agent_loop":
        raise RuntimeError("Production agent loop unavailable")
    if ga.GenericAgentHandler.__module__ != "ga":
        raise RuntimeError("Production GenericAgentHandler unavailable")
    config = json.loads((source / "mykey.json").read_text(encoding="utf-8"))[state["profile_name"]]
    if config["model"] != "claude-opus-4-8":
        raise RuntimeError("Task profile/model mismatch")
    backend = llmcore.NativeClaudeSession(cfg=config)
    backend.history = copy.deepcopy(state["backend_history"])
    backend._session_id = state["provider_metadata_identity"]["session_id"]
    backend._device_id = state["provider_metadata_identity"]["device_id"]
    client = llmcore.NativeToolClient(backend)
    client._pending_tool_ids = list(state["native_tool_client_pending_tool_ids"])
    llmcore.compress_history_tags._cd = 30
    parent = SimpleNamespace(
        llmclient=client, verbose=False, task_dir=str(task_dir),
        intervene=None, extrakeyinfo=None, research_condition=None,
        monitor_runtime=None, obligation_ledger=None, evidence_completion_kernel=None,
        completion_decision_callback=None, completion_proposal_checkpoint_callback=None,
        research_checkpoint_callback=None, _turn_end_hooks={},
    )
    handler = ga.GenericAgentHandler(parent, last_history=copy.deepcopy(state["history_info"]), cwd=str(cwd))
    handler.working = copy.deepcopy(state["handler_working_state"])
    handler.current_turn = 30
    system_text = state["system"][0]["text"]
    suffix = "\n\n" + client._thinking_prompt()
    if not system_text.endswith(suffix):
        raise RuntimeError("Production system/protocol suffix differs")
    system_prompt = system_text[:-len(suffix)]
    wrapper = ProductionBootstrapClient(client, system_prompt=system_prompt,
        initial_user_input=original_task, next_prompt=state["turn30_next_prompt"],
        turn30_tool_result=state["turn30_tool_result"], tools=state["tools"], capture=capture)
    return agent_loop, ga, llmcore, backend, client, handler, wrapper, system_prompt
