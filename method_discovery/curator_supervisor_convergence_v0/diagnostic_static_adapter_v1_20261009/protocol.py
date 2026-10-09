"""Static diagnostic provider/tool loop. No Task control leaves this module."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import time

import requests

from .adapter import CONTROL, canonical, request, save_json, sha, validate_args
from .docker_tool import DockerToolPort
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009.freeze_inputs import REPO

sys.path.insert(0, str(REPO / "GenericAgent-main"))
from monitor_agent_core.actions import MonitorAction, ToolOutcome  # noqa: E402
from monitor_agent_core.loop import MonitorLoopError, run_review  # noqa: E402
from monitor_agent_core.provider import (  # noqa: E402
    ModelResponse, MonitorProviderClient, ProviderError, ToolCall,
)


class StaticProtocolError(RuntimeError):
    pass


class StaticBudgetExhausted(RuntimeError):
    pass


RUN_BUDGET = {"model_turns_per_diagnostic": 300,
              "provider_transport_retries_after_ambiguous_failure": 0,
              "new_code_run_timeout_max_seconds": 300,
              "code_run_poll_wait_max_seconds": 5,
              "total_tool_call_cap": None, "total_tool_wait_cap": None,
              "diagnostic_wall_cap_seconds": None}


def ordinary_tools(frozen: dict) -> list[dict]:
    """Reverse only the production Anthropic tool projection."""
    return [{"type": "function", "function": {"name": item["name"],
            "description": item["description"], "parameters": item["input_schema"]}}
            for item in frozen["tools"]]


class Audit:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=False)
        self.path = root / "events.jsonl"

    def record(self, kind: str, **data):
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"time": time.time(), "kind": kind, **data},
                                    ensure_ascii=False, default=str) + "\n")


class StaticClient(MonitorProviderClient):
    """Production request assembly/parser/history, with a fail-before-send gate."""
    def __init__(self, config: dict, frozen: dict, audit: Audit, transport=None):
        super().__init__("claude_monitor_opus48", config)
        if self.provider != "anthropic" or self.model != "claude-opus-4-8":
            raise StaticProtocolError("Frozen model/provider unavailable")
        self.max_retries = 0  # Ambiguous stream/transport completion is never resent.
        self.frozen = copy.deepcopy(frozen)
        self.audit = audit
        self.transport = transport or requests.post
        self.first = True
        self.request_count = 0
        self.outer_cycles = 0
        self.accepted_responses = 0
        self.expected_history = copy.deepcopy(frozen["messages"])
        self.seen_tool_ids = set()
        self.started = time.monotonic()
        self.system = frozen["system"]
        self.restore_history(frozen["messages"])

    def _request_once(self, tools):
        if self.outer_cycles > RUN_BUDGET["model_turns_per_diagnostic"]:
            raise StaticBudgetExhausted("model-turn ceiling")
        url, headers, payload = self._anthropic_request(tools)
        if self.config.get("transport_route"):
            headers["x-model-route"] = self.config["transport_route"]
        if self.first:
            if payload != self.frozen:
                raise StaticProtocolError("First provider payload differs from frozen request")
        else:
            before = self.expected_history
            now = payload.get("messages")
            if (payload.get("system") != self.frozen["system"] or
                    payload.get("tools") != self.frozen["tools"] or
                    {k: v for k, v in payload.items() if k != "messages"} !=
                    {k: v for k, v in self.frozen.items() if k != "messages"} or
                    not isinstance(now, list) or now[:len(before)] != before or
                    len(now) != len(before) + 1 or now[-1].get("role") != "user"):
                raise StaticProtocolError("Subsequent request is not prior history plus one local result")
            outstanding = {block.get("id") for block in before[-1].get("content", [])
                           if block.get("type") == "tool_use"}
            results = [block for block in now[-1].get("content", [])
                       if block.get("type") == "tool_result"]
            if any(block.get("tool_use_id") not in outstanding for block in results):
                raise StaticProtocolError("Tool result has no prior tool_use identity")
        index = self.request_count + 1
        self.audit.record("provider_pre_send", index=index, sha256=sha(canonical(payload)))
        save_json(self.audit.root / f"request_{index:02d}.json", payload)
        self.request_count = index
        raw = self.audit.root / f"stream_{index:02d}.sse"
        try:
            with self.transport(url, headers=headers, json=payload, stream=True,
                                timeout=(self.connect_timeout, self.read_timeout),
                                proxies=self.proxies, verify=self.verify) as response:
                self.audit.record("response_headers", index=index, status_code=response.status_code)
                if response.status_code >= 400:
                    raise ProviderError(f"HTTP status {response.status_code}")
                def lines():
                    with raw.open("wb") as stream:
                        for line in response.iter_lines():
                            if isinstance(line, str):
                                line = line.encode("utf-8")
                            stream.write(line + b"\n")
                            if line.startswith(b"data:") and line[5:].strip() != b"[DONE]":
                                try: json.loads(line[5:].strip())
                                except (ValueError, UnicodeDecodeError) as exc:
                                    raise StaticProtocolError("Malformed SSE data") from exc
                            yield line
                blocks, usage = self._parse_anthropic(lines())
        except Exception as exc:
            self.audit.record("provider_incomplete_or_failed", index=index,
                              error_type=type(exc).__name__, raw_stream_exists=raw.exists())
            raise
        if self.last_response_metadata.get("stop_reason") not in {"tool_use", "end_turn"}:
            raise StaticProtocolError("Incomplete or unsupported provider stop reason")
        ids = [block.get("id") for block in blocks if block.get("type") == "tool_use"]
        if (any(not value or value in self.seen_tool_ids for value in ids) or
                len(set(ids)) != len(ids)):
            raise StaticProtocolError("Duplicate or empty tool_use identity")
        if any(block.get("type") == "tool_use" and
               (not isinstance(block.get("input"), dict) or "_raw" in block["input"])
               for block in blocks):
            raise StaticProtocolError("Incomplete tool JSON in completed stream")
        if sum(block.get("name") in CONTROL for block in blocks
               if block.get("type") == "tool_use") > 1:
            raise StaticProtocolError("Conflicting control proposals in one response")
        self.seen_tool_ids.update(ids)
        self.accepted_responses += 1
        self.audit.record("provider_response", index=index, blocks=blocks,
                          usage=usage, stop_reason=self.last_response_metadata.get("stop_reason"),
                          raw_stream_sha256=sha(raw.read_bytes()))
        return blocks, usage

    def complete(self, messages, tools):
        self.outer_cycles += 1
        self.audit.record("outer_model_cycle", cycle=self.outer_cycles)
        if self.first:
            if (messages[0].get("content") != self.frozen["system"] or
                    self._anthropic_request(tools)[2] != self.frozen):
                raise StaticProtocolError("Bootstrap system/tool schema mismatch")
            blocks, usage = self._request_batch(tools)
            self.first = False
            self.history.append({"role": "assistant", "content": blocks})
            self.expected_history = self.export_history()
            self.usage_records.append(dict(usage))
            return ModelResponse("\n".join(b.get("text", "") for b in blocks if b["type"] == "text"),
                                 [ToolCall(b["id"], b["name"], json.dumps(b["input"], ensure_ascii=False))
                                  for b in blocks if b["type"] == "tool_use"], usage)
        response = super().complete(messages, tools)
        self.expected_history = self.export_history()
        return response


class StaticDispatch:
    def __init__(self, frozen: dict, port: DockerToolPort, audit: Audit):
        self.schema = {item["name"]: item for item in frozen["tools"]}
        self.port, self.audit = port, audit
        self.calls, self.polls, self.wait_seconds = 0, 0, 0.0

    def __call__(self, name: str, arguments: dict) -> ToolOutcome:
        self.calls += 1
        if name == "code_run" and isinstance(arguments, dict) and arguments.get("session_id"):
            self.polls += 1
        if name not in self.schema or not validate_args(self.schema[name], arguments):
            result = {"status": "error", "reason": "invalid_tool_schema"}
            self.audit.record("tool_validation_error", name=name, arguments=arguments, result=result)
            return ToolOutcome(result)
        if name in CONTROL:
            kind = {"wait": "wait_proposal", "intervene": "intervention_proposal",
                    "allow_complete": "release_proposal"}[name]
            self.audit.record("control_proposal", name=name, arguments=arguments, disposition=kind)
            return ToolOutcome({"status": "proposal_only", "executed": False},
                               action=MonitorAction(kind, {}))
        began = time.monotonic()
        try:
            result = self.port.execute(name, arguments)
        except Exception as exc:
            result = {"status": "execution_unconfirmed", "error_type": type(exc).__name__}
        elapsed = time.monotonic() - began
        if name == "code_run":
            self.wait_seconds += elapsed
        self.audit.record("tool_execution", name=name, arguments=arguments,
                          result=result, seconds=elapsed)
        return ToolOutcome(result)


def run_static(scene: str, arm: str, config: dict, fixture: Path, audit: Audit,
               transport=None) -> dict:
    frozen = request(scene, arm)
    client = StaticClient(config, frozen, audit, transport)
    port = DockerToolPort(fixture)
    dispatch = StaticDispatch(frozen, port, audit)
    tools = ordinary_tools(frozen)
    started = time.monotonic()
    try:
        action = run_review(client, frozen["system"], "[frozen initial request]", tools,
                            dispatch, max_turns=RUN_BUDGET["model_turns_per_diagnostic"],
                            audit=lambda event, **data: audit.record("loop_" + event, **data))
        terminal = action.kind
    except (MonitorLoopError, StaticBudgetExhausted) as exc:
        terminal = "valid_capped"
        audit.record("budget_terminal", reason=type(exc).__name__)
    except Exception as exc:
        terminal = "protocol_or_infrastructure_failure"
        audit.record("failed_terminal", error_type=type(exc).__name__)
    finally:
        try:
            port.close()
        except Exception as exc:
            terminal = "protocol_or_infrastructure_failure"
            audit.record("cleanup_failed", error_type=type(exc).__name__)
    result = {"scene": scene, "arm": arm, "terminal": terminal,
              "provider_requests": client.request_count,
              "transport_retries": 0, "model_turns": client.outer_cycles,
              "accepted_responses": client.accepted_responses,
              "control_outcome": "no_terminal" if terminal == "valid_capped" else terminal,
              "tool_calls": dispatch.calls, "tool_polls": dispatch.polls,
              "tool_wait_seconds": dispatch.wait_seconds,
              "wall_seconds": time.monotonic() - started,
              "usage": client.usage_records,
              "history_sha256": sha(canonical(client.export_history()))}
    save_json(audit.root / "result.json", result)
    return result
