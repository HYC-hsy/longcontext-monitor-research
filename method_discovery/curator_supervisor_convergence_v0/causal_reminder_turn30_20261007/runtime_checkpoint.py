"""Zero-network reconstruction of the deployed Task Agent's turn-31 runtime.

The archived turn-31 body is an equality oracle only. State is recovered from
the preceding SHA-bound request, public turn-30 tool events, and deployed code.
"""

from __future__ import annotations

import copy
import importlib
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

from .materialize import sha_file
from .reconstruct_next_request import (PREVIOUS_ID, PREVIOUS_SHA256, NEXT_ID,
                                        NEXT_SHA256, raw_request, turn30_events, sha)


DEPLOYED_SOURCE = Path(r"E:\LongContext\long_context_bench\output\crs_rhr_rer_fyne_mechanism_gate\isolated_bundles\crs-rhr-rer-v0-fyne-bji-high-budget-r1\source")
EXPECTED_SOURCE_SHA256 = {
    "llmcore.py": "4e229383a806bca81fc190053482fa2ffd439735df94e53d23a92fb771d92518",
    "agent_loop.py": "1bcd38b9213c6d444d65c46a4612349a90ed9a3a0ed67e61e1acaebff6d9b262",
    "ga.py": "189c2272545b08dc61fd26a645df0ae0d0dbc07f0f62c8b713bb4f9a34bcb05a",
    "mykey.json": "c3462b8d06113b5398ecb7aa6f8d22dd19584f834c3336426457ab0f29069764",
}


def _source_hashes() -> dict[str, str]:
    result = {name: sha_file(DEPLOYED_SOURCE / name) for name in EXPECTED_SOURCE_SHA256}
    for name, expected in EXPECTED_SOURCE_SHA256.items():
        if expected and result[name] != expected:
            raise RuntimeError(f"Deployed Task Agent source changed: {name}")
    return result


def recovered_state() -> dict:
    _source_hashes()
    previous = raw_request(PREVIOUS_ID, PREVIOUS_SHA256)
    before, after = turn30_events()
    history = copy.deepcopy(previous["messages"])
    # NativeClaudeSession.raw_ask adds these markers to a request-local copy.
    # They are not persisted in backend.history (llmcore.py, raw_ask).
    decorated = []
    for index, item in enumerate(history):
        for block_index, block in enumerate(item["content"]):
            if "cache_control" in block:
                if item["role"] != "user" or block_index != len(item["content"]) - 1:
                    raise RuntimeError("Unexpected cache-control history decoration")
                if block.pop("cache_control") != {"type": "ephemeral"}:
                    raise RuntimeError("Unexpected cache-control marker")
                decorated.append(index)
    if decorated != [46, 48]:
        raise RuntimeError("Prior request cache-control positions changed")
    call = before["tool_calls"][0]
    history.append({"role": "assistant", "content": [
        {"type": "text", "text": before["text"]},
        {"type": "tool_use", "id": call["id"], "name": call["name"],
         "input": {k: v for k, v in call["args"].items() if not k.startswith("_")}},
    ]})
    if len(history) != 50:
        raise RuntimeError("Pre-turn31 backend history length changed")
    prompt = after["next_prompt"]
    match = re.search(r"<history>\n(.*?)\n</history>\nCurrent turn: 30\n", prompt, re.DOTALL)
    if not match:
        raise RuntimeError("Public turn-30 anchor history not recoverable")
    history_info_before_summary = match.group(1).split("\n")
    summary_match = re.search(r"<summary>(.*?)</summary>", before["text"], re.DOTALL)
    if not summary_match:
        raise RuntimeError("Turn-30 summary not recoverable")
    if str(DEPLOYED_SOURCE) not in sys.path:
        sys.path.insert(0, str(DEPLOYED_SOURCE))
    ga = importlib.import_module("ga")
    summary = ga.smart_format(summary_match.group(1).strip().replace("\n", ""), max_str_len=80)
    history_info = history_info_before_summary + ["[Agent] " + summary]
    # Re-run the deployed handler's anchor renderer on the recovered pre-summary
    # state. The turn-30 tool generated this prefix before turn_end_callback
    # appended its summary to history_info.
    handler = ga.GenericAgentHandler.__new__(ga.GenericAgentHandler)
    handler.history_info = history_info_before_summary
    handler.current_turn = 30
    handler.working = {"key_info": call["args"]["key_info"], "passed_sessions": 0}
    handler.parent = SimpleNamespace(verbose=False)
    if not prompt.startswith(handler._get_anchor_prompt()):
        raise RuntimeError("Production handler anchor does not reproduce public turn-30 prompt")
    metadata = json.loads(previous["metadata"]["user_id"])
    config = json.loads((DEPLOYED_SOURCE / "mykey.json").read_text(encoding="utf-8"))[
        "native_claude_cc_vibe_opus48"]
    if config["model"] != previous["model"]:
        raise RuntimeError("Task profile/model mismatch")
    if any("related_sop" in tool["args"] for row in jsonl_public_turns()
           for tool in row.get("tool_calls", []) if tool["name"] == "update_working_checkpoint"):
        raise RuntimeError("Working-state related_sop requires separate recovery")
    return {
        "backend_history": history,
        "backend_history_sha256": sha(history),
        "history_info": history_info,
        "history_info_sha256": sha(history_info),
        "handler_current_turn": 30,
        "handler_working_state": {"key_info": call["args"]["key_info"], "passed_sessions": 0},
        "agent_runner_turn_offset": 0,
        "next_task_turn": 31,
        "native_tool_client_pending_tool_ids": [call["id"]],
        "system": previous["system"],
        "tools": previous["tools"],
        "profile_name": "native_claude_cc_vibe_opus48",
        "profile_file_sha256": sha_file(DEPLOYED_SOURCE / "mykey.json"),
        "profile_public_semantics": {k: config[k] for k in
                                     ("model", "thinking_type", "temperature", "max_tokens", "max_retries")},
        "api_mode": "messages",
        "stream": previous["stream"],
        "context_win_characters": config.get("context_win", 30000),
        "task_prompt_language": "en",
        "provider_metadata_identity": metadata,
        "request_local_cache_control_positions": decorated,
        "source_file_sha256": _source_hashes(),
        "turn30_tool_result": after["tool_results"][0],
        "turn30_next_prompt": prompt,
    }


def jsonl_public_turns() -> list[dict]:
    from .materialize import PUBLIC_EVENTS, jsonl
    return [row for row in jsonl(PUBLIC_EVENTS) if row.get("task_turn", 999) <= 30]


def dry_run_before_network(state: dict) -> tuple[dict, dict]:
    """Call the deployed NativeToolClient/NativeClaudeSession path, cut at send."""
    if str(DEPLOYED_SOURCE) not in sys.path:
        sys.path.insert(0, str(DEPLOYED_SOURCE))
    llmcore = importlib.import_module("llmcore")
    config = json.loads((DEPLOYED_SOURCE / "mykey.json").read_text(encoding="utf-8"))[
        "native_claude_cc_vibe_opus48"]
    # The offline sink is installed before constructing or driving the client.
    class StopBeforeNetwork(Exception):
        pass
    capture = {}
    original_send = llmcore._stream_with_retry
    def stop_before_network(_session, _url, _headers, payload, _parse_fn):
        capture["payload"] = copy.deepcopy(payload)
        raise StopBeforeNetwork
    llmcore._stream_with_retry = stop_before_network
    previous_lang = os.environ.get("GA_LANG")
    os.environ["GA_LANG"] = "en"
    try:
        backend = llmcore.NativeClaudeSession(cfg=config)
        backend.history = copy.deepcopy(state["backend_history"])
        backend._session_id = state["provider_metadata_identity"]["session_id"]
        backend._device_id = state["provider_metadata_identity"]["device_id"]
        client = llmcore.NativeToolClient(backend)
        client._pending_tool_ids = list(state["native_tool_client_pending_tool_ids"])
        system_text = state["system"][0]["text"]
        protocol_suffix = "\n\n" + client._thinking_prompt()
        if not system_text.endswith(protocol_suffix):
            raise RuntimeError("Deployed Task system/protocol suffix mismatch")
        system_text = system_text[:-len(protocol_suffix)]
        tool_result = state["turn30_tool_result"]
        messages = [{"role": "system", "content": system_text},
                    {"role": "user", "content": state["turn30_next_prompt"],
                     "tool_results": [tool_result]}]
        generator = client.chat(messages, tools=copy.deepcopy(state["tools"]))
        try:
            next(generator)
        except StopBeforeNetwork:
            pass
        else:
            raise RuntimeError("Production request path did not stop before network")
        if "payload" not in capture:
            raise RuntimeError("Production request payload not captured")
        return capture["payload"], {
            "network_send_attempted": False,
            "request_builder": "deployed llmcore.NativeToolClient.chat -> NativeClaudeSession.ask/raw_ask",
            "cut_point": "_stream_with_retry before socket/provider send",
            "pending_tool_ids_after_request_build": list(client._pending_tool_ids),
            "backend_history_after_request_build_sha256": sha(backend.history),
        }
    finally:
        llmcore._stream_with_retry = original_send
        if previous_lang is None:
            os.environ.pop("GA_LANG", None)
        else:
            os.environ["GA_LANG"] = previous_lang


def certify() -> tuple[dict, dict, dict]:
    state = recovered_state()
    generated, execution = dry_run_before_network(state)
    original = raw_request(NEXT_ID, NEXT_SHA256)
    fields = sorted(set(generated) | set(original))
    mismatches = [field for field in fields if generated.get(field) != original.get(field)]
    report = {
        "model_visible_equal": not mismatches,
        "exact_equal_fields": [field for field in fields if field not in mismatches],
        "ignored_transport_fields": [],
        "mismatches": mismatches,
        "original_raw_bytes_sha256": NEXT_SHA256,
        "original_canonical_sha256": sha(original),
        "generated_canonical_sha256": sha(generated),
        **execution,
    }
    return state, generated, report
