"""Production provider assembly/parser with research-only exact send and raw capture."""

from __future__ import annotations

import copy
import json
from pathlib import Path

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
        blocks, usage = self._request(tools)
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
        try:
            with self.session.post(url, headers=headers, json=payload, stream=True,
                                   timeout=(self.connect_timeout, self.read_timeout),
                                   proxies=self.proxies, verify=self.verify) as response:
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
                    with stream_file.open("wb") as stream:
                        for line in response.iter_lines():
                            if isinstance(line, str):
                                line = line.encode("utf-8")
                            stream.write(line + b"\n")
                            if line.startswith(b"data:") and line[5:].strip() != b"[DONE]":
                                try:
                                    json.loads(line[5:].strip())
                                except (ValueError, UnicodeDecodeError) as exc:
                                    raise BridgeIntegrityError("Malformed SSE data") from exc
                            yield line

                blocks, usage = self._parse_anthropic(lines())
        except Exception as exc:
            self.audit.record("provider_incomplete_or_failed", index=index,
                              error_type=type(exc).__name__,
                              raw_stream_exists=stream_file.exists())
            raise
        if self.last_response_metadata.get("stream_complete") is not True:
            raise BridgeIntegrityError("Provider response not stream-complete")
        ids = [b.get("id") for b in blocks if b.get("type") == "tool_use"]
        if (any(not value or value in self.seen_ids for value in ids)
                or len(ids) != len(set(ids))
                or any(b.get("type") == "tool_use" and
                       (not isinstance(b.get("input"), dict) or "_raw" in b["input"])
                       for b in blocks)):
            raise BridgeIntegrityError("Malformed or duplicate tool-use envelope")
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
