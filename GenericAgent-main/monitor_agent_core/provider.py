"""Provider transport owned by Monitor Agent; no GenericAgent dependencies."""

from __future__ import annotations

import json
import hashlib
import re
import threading
import time
import uuid
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ModelResponse:
    content: str
    tool_calls: list[ToolCall]
    usage: dict


class ProviderError(RuntimeError):
    pass


def _url(base: str, path: str) -> str:
    base, path = base.rstrip("/"), path.strip("/")
    if base.endswith("$"):
        return base[:-1].rstrip("/")
    if base.endswith(path):
        return base
    return f"{base}/{path}" if re.search(r"/v\d+(/|$)", base) else f"{base}/v1/{path}"


def _claude_tools(tools):
    return [{
        "name": item["function"]["name"],
        "description": item["function"].get("description", ""),
        "input_schema": item["function"].get("parameters", {"type": "object", "properties": {}}),
    } for item in tools]


def _openai_tools(tools, responses_api):
    if not responses_api:
        return tools
    return [{"type": "function", **item["function"]} for item in tools]


class MonitorProviderClient:
    """Persistent provider history for one Monitor identity."""

    CONTROL_ACTIONS = {"wait", "intervene", "allow_complete"}

    def __init__(self, config_name: str, config: dict):
        self.config_name = config_name
        self.config = dict(config)
        self.api_key = self.config["apikey"]
        self.api_base = self.config["apibase"].rstrip("/")
        self.model = self.config.get("model", "")
        self.provider = self._provider_kind(config_name, self.config)
        self.api_mode = str(self.config.get("api_mode", "responses" if self.provider == "openai" else "messages"))
        self.max_tokens = int(self.config.get("max_tokens") or 8192)
        self.context_window = int(self.config.get("context_win") or 200000)
        self.history_char_limit = int(
            self.config.get("monitor_history_char_limit") or self.context_window * 3.5
        )
        self.history_target_chars = int(self.history_char_limit * 0.82)
        self.reasoning_effort = self.config.get("reasoning_effort")
        self.thinking_type = str(self.config.get("thinking_type") or "").lower()
        self.temperature = self.config.get("temperature", 1)
        self.connect_timeout = max(1, int(self.config.get("timeout", 10)))
        self.read_timeout = max(10, int(self.config.get("read_timeout", 300)))
        self.max_retries = max(0, int(self.config.get("max_retries", 2)))
        self.verify = self.config.get("verify", True)
        proxy = self.config.get("proxy")
        self.proxies = {"http": proxy, "https": proxy} if proxy else None
        self.system = ""
        self.history = []
        self.usage_records = []
        self.history_transforms = []
        self._active_lock = threading.Lock()
        self._active_response = None

    @staticmethod
    def _provider_kind(name, config):
        explicit = str(config.get("provider", "")).lower()
        if explicit in {"anthropic", "claude"}: return "anthropic"
        if explicit in {"openai", "oai"}: return "openai"
        lowered = f"{name} {config.get('model', '')}".lower()
        return "anthropic" if "claude" in lowered else "openai"

    def cancel_active_response(self) -> bool:
        with self._active_lock:
            response = self._active_response
        if response is None:
            return False
        try: response.close()
        except Exception: pass
        return True

    def history_measure(self) -> dict:
        encoded = json.dumps(self.history, ensure_ascii=False, default=str).encode("utf-8")
        return {
            "items": len(self.history), "characters": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }

    def export_history(self) -> list[dict]:
        return json.loads(json.dumps(self.history, ensure_ascii=False))

    def restore_history(self, history: list[dict]) -> None:
        self.history = json.loads(json.dumps(history, ensure_ascii=False))

    def record_tool_results(self, results: list[dict]) -> None:
        """Close tool calls in canonical history without starting another model turn."""
        if not results:
            return
        self.history.append({"role": "user", "content": [{
            "type": "tool_result",
            "tool_use_id": str(result.get("tool_use_id") or ""),
            "content": str(result.get("content") or ""),
        } for result in results]})

    @staticmethod
    def _bounded_block(value, limit=6000):
        if not isinstance(value, str) or len(value) <= limit:
            return value
        half = limit // 2
        return value[:half] + "\n[older tool output compacted]\n" + value[-half:]

    def _history_characters(self):
        return len(json.dumps(
            self.history, ensure_ascii=False, default=str
        ).encode("utf-8"))

    def _review_boundaries(self):
        """Return indexes after fully closed Monitor control-action reviews."""
        boundaries = []
        outstanding = set()
        terminal_pending = False
        for index, message in enumerate(self.history):
            if message.get("role") == "assistant":
                for block in message.get("content") or []:
                    if block.get("type") != "tool_use":
                        continue
                    call_id = str(block.get("id") or "")
                    if call_id:
                        outstanding.add(call_id)
                    if block.get("name") in self.CONTROL_ACTIONS:
                        terminal_pending = True
            elif message.get("role") == "user":
                for block in message.get("content") or []:
                    if block.get("type") == "tool_result":
                        outstanding.discard(str(block.get("tool_use_id") or ""))
                if terminal_pending and not outstanding:
                    boundaries.append(index + 1)
                    terminal_pending = False
        return boundaries

    def _compact_old_tool_results(self, start, stop):
        for message in self.history[start:stop]:
            if message.get("role") != "user":
                continue
            for block in message.get("content") or []:
                if block.get("type") == "tool_result":
                    block["content"] = self._bounded_block(block.get("content", ""))

    def _compact_history(self):
        before = self.history_measure()
        if before["characters"] <= self.history_char_limit:
            return

        # Review boundaries are defined by acknowledged control actions, not by
        # a fixed number of messages. Never split a tool call from its result.
        boundaries = self._review_boundaries()
        head_end = boundaries[0] if boundaries else 0
        recent_floor = max(head_end, len(self.history) - 16)
        old_end = max((value for value in boundaries if value <= recent_floor), default=head_end)
        self._compact_old_tool_results(head_end, old_end)
        removed = 0
        while self._history_characters() > self.history_target_chars:
            boundaries = self._review_boundaries()
            if not boundaries:
                break
            head_end = boundaries[0]
            removable = [
                value for value in boundaries[1:]
                if len(self.history) - value >= 16
            ]
            if not removable:
                break
            end = removable[0]
            del self.history[head_end:end]
            removed += end - head_end

        # An unusually large recent inspection result can itself exceed the
        # budget. Bound tool outputs outside the latest request without
        # rewriting signed thinking or provider reasoning items.
        if self._history_characters() > self.history_char_limit:
            boundaries = self._review_boundaries()
            head_end = boundaries[0] if boundaries else 0
            for message in self.history[head_end:-2]:
                if message.get("role") != "user":
                    continue
                for block in message.get("content") or []:
                    if block.get("type") == "tool_result":
                        block["content"] = self._bounded_block(block.get("content", ""), 12000)

        after = self.history_measure()
        self.history_transforms.append({
            "kind": "monitor_history_compaction",
            "before": before,
            "after": after,
            "removed_messages": removed,
            "char_limit": self.history_char_limit,
            "target_chars": self.history_target_chars,
        })

    def drain_telemetry(self):
        value = {
            "usage": list(self.usage_records),
            "history_transforms": list(self.history_transforms),
        }
        self.usage_records.clear()
        self.history_transforms.clear()
        return value

    def complete(self, messages: list[dict], tools: list[dict]) -> ModelResponse:
        user_blocks = []
        for message in messages:
            if message["role"] == "system":
                self.system = str(message.get("content") or "")
                continue
            for result in message.get("tool_results") or []:
                user_blocks.append({
                    "type": "tool_result", "tool_use_id": result.get("tool_use_id", ""),
                    "content": result.get("content", ""),
                })
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                user_blocks.append({"type": "text", "text": content})
        if not user_blocks:
            user_blocks = [{"type": "text", "text": "."}]
        self.history.append({"role": "user", "content": user_blocks})
        self._compact_history()
        blocks, usage = self._request(tools)
        if blocks:
            self.history.append({"role": "assistant", "content": blocks})
        text = "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        calls = [ToolCall(
            str(block.get("id") or uuid.uuid4().hex), str(block.get("name") or ""),
            json.dumps(block.get("input") or {}, ensure_ascii=False),
        ) for block in blocks if block.get("type") == "tool_use"]
        self.usage_records.append(dict(usage))
        return ModelResponse(text, calls, usage)

    def _request(self, tools):
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return self._request_once(tools)
            except (requests.Timeout, requests.ConnectionError, requests.exceptions.ChunkedEncodingError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(min(8, 1.5 * (2 ** attempt)))
        raise ProviderError(f"Provider request failed: {last_error}")

    def _request_once(self, tools):
        if self.provider == "anthropic":
            url, headers, payload = self._anthropic_request(tools)
            parser = self._parse_anthropic
        else:
            url, headers, payload = self._openai_request(tools)
            parser = self._parse_openai_responses if self.api_mode.startswith("response") else self._parse_openai_chat
        with requests.post(
            url, headers=headers, json=payload, stream=True,
            timeout=(self.connect_timeout, self.read_timeout), proxies=self.proxies, verify=self.verify,
        ) as response:
            with self._active_lock: self._active_response = response
            try:
                if response.status_code >= 400:
                    try: body = response.text[:500]
                    except Exception: body = ""
                    raise ProviderError(f"HTTP {response.status_code}: {body}")
                return parser(response.iter_lines())
            finally:
                with self._active_lock:
                    if self._active_response is response: self._active_response = None

    def _anthropic_request(self, tools):
        headers = {
            "Content-Type": "application/json", "anthropic-version": "2023-06-01",
            "Accept": "application/json", "user-agent": "longcontext-monitor/1.0",
        }
        if self.api_key.startswith("sk-ant-"): headers["x-api-key"] = self.api_key
        else: headers["authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model, "messages": self.history, "max_tokens": self.max_tokens,
            "stream": True, "system": self.system, "tools": _claude_tools(tools),
        }
        headers["anthropic-beta"] = ",".join([
            "interleaved-thinking-2025-05-14", "redact-thinking-2026-02-12",
            "context-management-2025-06-27", "effort-2025-11-24",
        ])
        if self.temperature != 1: payload["temperature"] = self.temperature
        if self.thinking_type == "adaptive" or self.reasoning_effort:
            payload["thinking"] = {"type": "adaptive"}
        if self.reasoning_effort:
            payload["output_config"] = {"effort": self.reasoning_effort}
        return _url(self.api_base, "messages") + "?beta=true", headers, payload

    def _openai_request(self, tools):
        headers = {
            "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
            "Accept": "text/event-stream", "User-Agent": "longcontext-monitor/1.0",
        }
        if self.api_mode.startswith("response"):
            payload = {
                "model": self.model, "input": self._responses_history(), "stream": True,
                "instructions": self.system, "tools": _openai_tools(tools, True),
                "include": ["reasoning.encrypted_content"],
            }
            if self.max_tokens: payload["max_output_tokens"] = self.max_tokens
            if self.reasoning_effort: payload["reasoning"] = {"effort": self.reasoning_effort}
            return _url(self.api_base, "responses"), headers, payload
        messages = [{"role": "system", "content": self.system}] + self._chat_history()
        payload = {"model": self.model, "messages": messages, "stream": True,
                   "stream_options": {"include_usage": True}, "tools": _openai_tools(tools, False)}
        if self.max_tokens: payload["max_completion_tokens"] = self.max_tokens
        if self.reasoning_effort: payload["reasoning_effort"] = self.reasoning_effort
        if self.temperature != 1: payload["temperature"] = self.temperature
        return _url(self.api_base, "chat/completions"), headers, payload

    def _chat_history(self):
        result = []
        for message in self.history:
            if message["role"] == "assistant":
                text = "\n".join(x.get("text", "") for x in message["content"] if x.get("type") == "text")
                calls = [{"id": x["id"], "type": "function", "function": {
                    "name": x["name"], "arguments": json.dumps(x.get("input") or {})
                }} for x in message["content"] if x.get("type") == "tool_use"]
                result.append({"role": "assistant", "content": text or None, "tool_calls": calls})
            else:
                texts = [x.get("text", "") for x in message["content"] if x.get("type") == "text"]
                if texts: result.append({"role": "user", "content": "\n".join(texts)})
                for block in message["content"]:
                    if block.get("type") == "tool_result":
                        result.append({"role": "tool", "tool_call_id": block["tool_use_id"], "content": block.get("content", "")})
        return result

    def _responses_history(self):
        result = []
        for message in self.history:
            if message["role"] == "assistant":
                text = "\n".join(x.get("text", "") for x in message["content"] if x.get("type") == "text")
                if text: result.append({"role": "assistant", "content": text})
                for block in message["content"]:
                    if block.get("type") == "openai_item": result.append(dict(block["item"]))
                    elif block.get("type") == "tool_use": result.append({
                        "type": "function_call", "call_id": block["id"], "name": block["name"],
                        "arguments": json.dumps(block.get("input") or {}),
                    })
            else:
                texts = [x.get("text", "") for x in message["content"] if x.get("type") == "text"]
                if texts: result.append({"role": "user", "content": "\n".join(texts)})
                for block in message["content"]:
                    if block.get("type") == "tool_result": result.append({
                        "type": "function_call_output", "call_id": block["tool_use_id"],
                        "output": block.get("content", ""),
                    })
        return result

    @staticmethod
    def _events(lines):
        for line in lines:
            if not line: continue
            text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
            if not text.startswith("data:"): continue
            data = text[5:].strip()
            if data == "[DONE]": return
            try: yield json.loads(data)
            except json.JSONDecodeError: continue

    def _parse_anthropic(self, lines):
        blocks, current, tool_json, usage = [], None, "", {}
        for event in self._events(lines):
            kind = event.get("type")
            if kind == "message_start": usage.update(event.get("message", {}).get("usage", {}) or {})
            elif kind == "content_block_start":
                block = event.get("content_block", {})
                if block.get("type") == "text": current = {"type": "text", "text": ""}
                elif block.get("type") == "thinking": current = {"type": "thinking", "thinking": "", "signature": ""}
                elif block.get("type") == "tool_use":
                    current = {"type": "tool_use", "id": block.get("id", ""), "name": block.get("name", ""), "input": {}}
                    tool_json = ""
            elif kind == "content_block_delta" and current:
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta": current["text"] += delta.get("text", "")
                elif delta.get("type") == "thinking_delta": current["thinking"] += delta.get("thinking", "")
                elif delta.get("type") == "signature_delta": current["signature"] += delta.get("signature", "")
                elif delta.get("type") == "input_json_delta": tool_json += delta.get("partial_json", "")
            elif kind == "content_block_stop" and current:
                if current["type"] == "tool_use":
                    try: current["input"] = json.loads(tool_json or "{}")
                    except json.JSONDecodeError: current["input"] = {"_raw": tool_json}
                blocks.append(current); current = None
            elif kind == "message_delta": usage.update(event.get("usage", {}) or {})
            elif kind == "error": raise ProviderError(str(event.get("error")))
        if current: blocks.append(current)
        return blocks, usage

    def _parse_openai_responses(self, lines):
        text, calls, usage, provider_items = "", {}, {}, {}
        for event in self._events(lines):
            kind = event.get("type")
            if kind == "response.output_text.delta": text += event.get("delta", "")
            elif kind == "response.output_item.added":
                item = event.get("item", {})
                if item.get("type") == "function_call":
                    index = event.get("output_index", 0)
                    calls[index] = {"type": "tool_use", "id": item.get("call_id", item.get("id", "")), "name": item.get("name", ""), "input": {}, "_args": ""}
                elif item.get("type") == "reasoning":
                    provider_items[event.get("output_index", 0)] = dict(item)
            elif kind == "response.output_item.done":
                item = event.get("item", {})
                if item.get("type") == "reasoning":
                    provider_items[event.get("output_index", 0)] = dict(item)
            elif kind == "response.function_call_arguments.delta":
                index = event.get("output_index", 0)
                if index in calls: calls[index]["_args"] += event.get("delta", "")
            elif kind == "response.function_call_arguments.done":
                index = event.get("output_index", 0)
                if index in calls: calls[index]["_args"] = event.get("arguments", calls[index]["_args"])
            elif kind == "response.completed": usage = event.get("response", {}).get("usage", {}) or {}
            elif kind == "error": raise ProviderError(str(event.get("error")))
        blocks = [{"type": "openai_item", "item": provider_items[index]} for index in sorted(provider_items)]
        if text: blocks.append({"type": "text", "text": text})
        for index in sorted(calls):
            call = calls[index]
            try: call["input"] = json.loads(call.pop("_args") or "{}")
            except json.JSONDecodeError: call["input"] = {"_raw": call.pop("_args")}
            blocks.append(call)
        return blocks, usage

    def _parse_openai_chat(self, lines):
        text, calls, usage = "", {}, {}
        for event in self._events(lines):
            usage.update(event.get("usage") or {})
            choice = (event.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            text += delta.get("content") or ""
            for item in delta.get("tool_calls") or []:
                index = item.get("index", 0)
                call = calls.setdefault(index, {"id": "", "name": "", "args": ""})
                call["id"] = item.get("id") or call["id"]
                function = item.get("function") or {}
                call["name"] += function.get("name") or ""
                call["args"] += function.get("arguments") or ""
        blocks = [{"type": "text", "text": text}] if text else []
        for index in sorted(calls):
            call = calls[index]
            try: inputs = json.loads(call["args"] or "{}")
            except json.JSONDecodeError: inputs = {"_raw": call["args"]}
            blocks.append({"type": "tool_use", "id": call["id"], "name": call["name"], "input": inputs})
        return blocks, usage
