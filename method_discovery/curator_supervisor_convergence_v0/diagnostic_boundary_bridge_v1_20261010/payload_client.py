"""Production provider assembly/parser with research-only exact send and raw capture."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import requests

from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.adapter import canonical
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.protocol import Audit
from . import bootstrap as _bootstrap  # ensures the deployed GenericAgent package is importable
from .freeze_inputs import NEW, digest

from monitor_agent_core.agent import CONTINUATION_MODE_PROMPT
from monitor_agent_core.ase_v0 import SYSTEM_PROMPT as ASE_SYSTEM_PROMPT
from monitor_agent_core.provider import (ModelResponse, MonitorProviderClient,
                                         ProviderError, HistoryCapacityError,
                                         ToolCall, _claude_tools)


class BridgeIntegrityError(RuntimeError):
    """An identity, archived response, or transport envelope is unusable."""


class AnthropicEnvelope:
    """Check the finite SSE block lifecycle before native parsing/dispatch."""

    def __init__(self):
        self.started = False
        self.finished = False
        self.open_index = None
        self.next_index = 0
        self.tool_ids = set()

    def feed(self, event):
        kind = event.get("type")
        if kind == "ping":
            return
        if kind == "error":
            return  # Native provider parser retains the remote error semantics.
        if self.finished:
            raise BridgeIntegrityError("SSE data after message_stop")
        if kind == "message_start":
            if self.started or self.open_index is not None:
                raise BridgeIntegrityError("Repeated/out-of-order message_start")
            self.started = True
        elif not self.started:
            raise BridgeIntegrityError("SSE content before message_start")
        elif kind == "content_block_start":
            index = event.get("index")
            if self.open_index is not None or type(index) is not int or index != self.next_index:
                raise BridgeIntegrityError("Overlapping/out-of-order content_block_start")
            block = event.get("content_block") or {}
            if block.get("type") not in {"text", "thinking", "redacted_thinking", "tool_use"}:
                raise BridgeIntegrityError("Unsupported Anthropic content block type")
            if block.get("type") == "tool_use":
                tool_id = block.get("id")
                if not isinstance(tool_id, str) or not tool_id or tool_id in self.tool_ids:
                    raise BridgeIntegrityError("Empty/duplicate tool_use id")
                self.tool_ids.add(tool_id)
            self.open_index = index
        elif kind in {"content_block_delta", "content_block_stop"}:
            if self.open_index is None or event.get("index") != self.open_index:
                raise BridgeIntegrityError("SSE delta/stop does not match open block")
            if kind == "content_block_stop":
                self.open_index = None
                self.next_index += 1
        elif kind == "message_delta":
            if self.open_index is not None:
                raise BridgeIntegrityError("message_delta before block_stop")
        elif kind == "message_stop":
            if self.open_index is not None:
                raise BridgeIntegrityError("message_stop with unclosed block")
            self.finished = True
        else:
            raise BridgeIntegrityError("Unknown Anthropic SSE event type")


class BoundaryClient(MonitorProviderClient):
    def __init__(self, config: dict, frozen: dict, audit: Audit, session):
        super().__init__("claude_monitor_opus48", config)
        if self.provider != "anthropic" or self.model != "claude-opus-4-8":
            raise BridgeIntegrityError("Frozen Supervisor model/provider mismatch")
        self.max_retries = 0
        self.recovery_deadline = None
        self.session = session
        self.frozen = copy.deepcopy(frozen)
        self.audit = audit
        self.first = True
        self.send_count = 0
        self.accepted_count = 0
        self.seen_ids = {b["id"] for m in frozen["messages"] for b in m["content"]
                         if b.get("type") == "tool_use"}
        self.previous_persistent_history = None
        self.previous_purpose = None
        self.failure_latch = None
        self.restore_history(frozen["messages"][:-1])
        self.system = frozen["system"]

    def complete(self, messages, tools):
        if not self.first:
            tools = self._linux_tool_port(tools)
            prepared = copy.deepcopy(messages)
            expected_base = self.frozen["system"][:-(len(NEW) + 2)]
            systems = [message for message in prepared if message.get("role") == "system"]
            if len(systems) > 1 or (systems and systems[0].get("content") != expected_base):
                raise BridgeIntegrityError("Native regular system/review mode drifted")
            if systems:
                systems[0]["content"] += "\n\n" + NEW
            elif self.system != self.frozen["system"]:
                raise BridgeIntegrityError("System context lost between native model turns")
            return super().complete(prepared, tools)
        # The historical review is already between turns. Its final ordinary
        # user/tool-result message is in restored History; run_review's newly
        # synthesized wake is intentionally not another provider-visible turn.
        self.complete_calls += 1
        expected_base = self.frozen["system"][:-(len(NEW) + 2)]
        if len(messages) < 2 or messages[0].get("content") != expected_base:
            raise BridgeIntegrityError("Historical bootstrap system differs")
        prepare = getattr(self, "prepare_active_context", None)
        historical_context = self.frozen["messages"][-1]["content"][0]["text"]
        self.prepare_active_context = lambda: historical_context
        try:
            blocks, usage = self._request(tools)
        finally:
            self.prepare_active_context = prepare
        delivered = getattr(self, "first_context_delivered", None)
        if delivered is not None:
            delivered()
        self.history.append({"role": "assistant", "content": blocks})
        self.usage_records.append(dict(usage))
        self.first = False
        return ModelResponse("\n".join(b.get("text", "") for b in blocks if b["type"] == "text"),
                             [ToolCall(b["id"], b["name"], json.dumps(b["input"], ensure_ascii=False))
                              for b in blocks if b["type"] == "tool_use"], usage)

    def _linux_tool_port(self, tools):
        projected = _claude_tools(tools)
        if projected == self.frozen["tools"]:
            return tools
        adapted = copy.deepcopy(tools)
        native = next((item for item in adapted if item["function"]["name"] == "code_run"), None)
        if native is None:
            raise BridgeIntegrityError("Native code_run tool missing")
        enum = native["function"]["parameters"]["properties"]["type"]["enum"]
        if enum != ["python", "powershell"]:
            raise BridgeIntegrityError("Unexpected host code_run interpreter schema")
        enum[:] = ["python", "bash"]
        if _claude_tools(adapted) != self.frozen["tools"]:
            raise BridgeIntegrityError("Native schema differs beyond the Linux interpreter port")
        self.audit.record("linux_tool_port_applied", change="code_run.type.enum",
                          from_values=["python", "powershell"], to_values=["python", "bash"])
        return adapted

    def _check_payload(self, payload, tools):
        purpose = getattr(self, "request_purpose", "review")
        if self.first and purpose == "review":
            if payload != self.frozen:
                raise BridgeIntegrityError("First transport payload differs from frozen full request")
            self.first_request_sha256 = digest(canonical(payload))
        elif purpose == "review":
            drift = [field for field in self.frozen if field != "messages" and
                     payload.get(field) != self.frozen.get(field)]
            if drift:
                raise BridgeIntegrityError("Regular review model/system/tool fields drifted: " +
                                           ",".join(drift))
        elif purpose in {"continuation", "format_repair"}:
            expected_system = ASE_SYSTEM_PROMPT + "\n\n" + CONTINUATION_MODE_PROMPT
            if payload["system"] != expected_system or payload["tools"] != []:
                raise BridgeIntegrityError("Native maintenance request contract drifted")
        else:
            raise BridgeIntegrityError("Unexpected provider request purpose")
        if payload["messages"] != self.history:
            raise BridgeIntegrityError("Provider payload is not the live native History")
        if self.previous_persistent_history is not None:
            before = self.previous_persistent_history
            after = payload["messages"]
            if after[:len(before)] != before:
                changes = self.history_transforms
                native_repair = (purpose in {"continuation", "format_repair"} and
                                 self.previous_purpose in {"continuation", "format_repair"} and
                                 len(after) == len(before) and after[:-1] == before[:-1] and
                                 after[-1].get("role") == "user" and before[-1].get("role") == "user")
                if not changes and not getattr(self, "bridge_history_boundary", None) and not native_repair:
                    raise BridgeIntegrityError("Unexplained provider-history transform")
                self.audit.record("history_transform_before_send",
                                  reason=("native_continuation_format_repair" if native_repair else
                                          getattr(self, "bridge_history_boundary", None)) or
                                  "native_compaction_or_archival",
                                  previous_sha256=digest(canonical(before)),
                                  current_sha256=digest(canonical(after)),
                                  native_transforms=copy.deepcopy(changes))
                self.bridge_history_boundary = None
        self.audit.record("provider_pre_send", index=self.send_count + 1, purpose=purpose,
                          request_sha256=digest(canonical(payload)),
                          history_sha256=digest(canonical(payload["messages"])),
                          review_id=self.review_id)

    def _request_once(self, tools):
        url, headers, payload = self._anthropic_request(tools)
        if self.config.get("transport_route"):
            headers["x-model-route"] = self.config["transport_route"]
        self._check_payload(payload, tools)
        index = self.send_count + 1
        request_file = self.audit.root / f"request_{index:04d}.json"
        request_file.write_bytes(canonical(payload))
        self.send_count = index
        stream_file = self.audit.root / f"stream_{index:04d}.sse"
        phase = "connect_or_tls_handshake"
        envelope = AnthropicEnvelope()
        try:
            with self.session.post(url, headers=headers, json=payload, stream=True,
                                   timeout=(self.connect_timeout, self.read_timeout),
                                   proxies=self.proxies, verify=self.verify) as response:
                phase = "response_headers"
                self.audit.record("response_headers", index=index,
                                  status_code=response.status_code)
                if response.status_code >= 400:
                    try:
                        problem = response.json().get("error", {})
                        codes = [problem.get("type"), problem.get("code")]
                    except (ValueError, AttributeError):
                        codes = []
                    if any(str(code).lower() in {"context_length_exceeded",
                                                      "context_window_exceeded"}
                           for code in codes):
                        self.audit.record("provider_context_capacity", index=index,
                                          code_types=[str(code) for code in codes if code])
                        raise HistoryCapacityError("Frozen provider context capacity exhausted")
                    raise ProviderError(f"HTTP status {response.status_code}")

                def lines():
                    nonlocal phase
                    phase = "sse_read"
                    with stream_file.open("wb") as stream:
                        for line in response.iter_lines():
                            if isinstance(line, str):
                                line = line.encode("utf-8")
                            stream.write(line + b"\n")
                            if line.startswith(b"data:") and line[5:].strip() != b"[DONE]":
                                try:
                                    event = json.loads(line[5:].strip())
                                except (ValueError, UnicodeDecodeError) as exc:
                                    raise BridgeIntegrityError("Malformed SSE data") from exc
                                if not isinstance(event, dict):
                                    raise BridgeIntegrityError("Non-object SSE data")
                                envelope.feed(event)
                            yield line

                stream_lines = lines()
                blocks, usage = self._parse_anthropic(stream_lines)
                # Native parsing stops at message_stop. Finish reading the
                # actual envelope before accepting any tool calls or archiving
                # the stream as complete.
                for _ in stream_lines:
                    pass
                if not envelope.finished:
                    raise BridgeIntegrityError("SSE message_stop was not observed")
        except Exception as exc:
            chain = []
            cursor = exc
            while cursor is not None and len(chain) < 12:
                chain.append(type(cursor).__name__)
                cursor = cursor.__cause__ or cursor.__context__
            if isinstance(exc, BridgeIntegrityError) or (
                    phase == "sse_read" and not envelope.finished):
                self.failure_latch = "integrity"
            elif (isinstance(exc, (requests.RequestException, OSError)) or
                  isinstance(exc, ProviderError) and not isinstance(exc, HistoryCapacityError)):
                self.failure_latch = "transport_or_io"
            self.audit.record("provider_incomplete_or_failed", index=index,
                              error_type=type(exc).__name__,
                              cause_types=chain, phase=phase,
                              response_headers_received=phase != "connect_or_tls_handshake",
                              server_execution="unknown", raw_stream_exists=stream_file.exists())
            raise
        if self.last_response_metadata.get("stream_complete") is not True:
            raise BridgeIntegrityError("Provider response not stream-complete")
        ids = [b.get("id") for b in blocks if b.get("type") == "tool_use"]
        if (any(not value or value in self.seen_ids for value in ids)
                or len(ids) != len(set(ids))):
            self.failure_latch = "integrity"
            raise BridgeIntegrityError("Malformed or duplicate tool-use envelope")
        for block in blocks:
            if block.get("type") == "tool_use" and not isinstance(block.get("input"), dict):
                self.audit.record("model_tool_parameter_nonobject", index=index,
                                  tool_use_id=block["id"], input_type=type(block["input"]).__name__)
                block["input"] = {"_raw": block["input"]}
        self.seen_ids.update(ids)
        self.accepted_count += 1
        purpose = getattr(self, "request_purpose", "review")
        self.previous_persistent_history = copy.deepcopy(
            payload["messages"][:-1] if purpose == "review" and tools else payload["messages"])
        self.previous_purpose = purpose
        self.audit.record("provider_response", index=index, blocks=blocks, usage=usage,
                          metadata=copy.deepcopy(self.last_response_metadata),
                          raw_stream_sha256=digest(stream_file.read_bytes()))
        return blocks, usage
