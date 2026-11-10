"""Responses-API transport for the frozen read-context PMA candidate.

Only the provider envelope is adapted. The PMA prompts, tool execution,
knowledge bank, history trimming and reminder parser remain in their owners.
"""

from __future__ import annotations

import json
import copy
from types import SimpleNamespace
from typing import Any

from harbor.llms.base import BaseLLM, LLMResponse


def public_reasoning_summary(output: list[dict], *, requested: bool) -> dict:
    """Project only the Responses API's documented display-summary fields."""
    texts = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "reasoning":
            continue
        summary = item.get("summary")
        if not isinstance(summary, list):
            continue
        texts.extend(block["text"] for block in summary
                     if isinstance(block, dict) and block.get("type") == "summary_text"
                     and isinstance(block.get("text"), str) and block["text"].strip())
    return {"request_status": "requested" if requested else "not_requested",
            "result_status": "returned" if texts else "not_returned",
            "source": "openai.responses.reasoning.summary_text", "texts": texts}


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        if any(not isinstance(item, dict) or item.get("type") != "text" or
               not isinstance(item.get("text"), str) for item in value):
            raise ValueError("unsupported PMA history content in Responses adapter")
        return "\n".join(item["text"] for item in value)
    raise ValueError("invalid PMA history content in Responses adapter")


def response_input(history: list[dict], prompt: str) -> list[dict]:
    """Preserve visible role order, native call IDs/receipts and opaque items."""
    if not isinstance(prompt, str):
        raise ValueError("PMA prompt must be text")
    items: list[dict] = []
    for row in history:
        if not isinstance(row, dict):
            raise ValueError("PMA history row must be an object")
        role = row.get("role")
        if role == "user":
            items.append({"role": "user", "content": _text(row.get("content", ""))})
        elif role == "tool":
            call_id = row.get("tool_call_id")
            if not isinstance(call_id, str) or not call_id:
                raise ValueError("PMA tool result lacks call ID")
            items.append({"type": "function_call_output", "call_id": call_id,
                          "output": _text(row.get("content", ""))})
        elif role == "assistant":
            opaque = row.get("_openai_output_items")
            if opaque is not None:
                if not isinstance(opaque, list) or not opaque:
                    raise ValueError("PMA opaque Responses history invalid")
                # The GA policy may have compressed the visible text or tool
                # arguments since the original response. Replay only opaque
                # reasoning verbatim; rebuild visible items from the *current*
                # history row so the actual request honors that compression.
                text_now = _text(row["content"]) if row.get("content") else ""
                current_calls = {}
                for call in row.get("tool_calls") or []:
                    if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
                        raise ValueError("PMA assistant tool call invalid")
                    fn = call["function"]
                    call_id = call.get("id")
                    if (not isinstance(call_id, str) or not call_id or
                            call_id in current_calls or
                            not isinstance(fn.get("name"), str) or
                            not isinstance(fn.get("arguments"), str)):
                        raise ValueError("PMA assistant tool call identity invalid")
                    current_calls[call_id] = fn
                emitted_message, emitted_calls = False, set()
                for prior_item in opaque:
                    if not isinstance(prior_item, dict):
                        raise ValueError("PMA opaque Responses item invalid")
                    kind = prior_item.get("type")
                    if kind == "reasoning":
                        items.append(copy.deepcopy(prior_item))
                    elif kind == "message":
                        if not emitted_message and text_now:
                            items.append({"role": "assistant", "content": text_now})
                        emitted_message = True
                    elif kind == "function_call":
                        call_id = prior_item.get("call_id")
                        fn = current_calls.get(call_id)
                        if fn is None or call_id in emitted_calls or fn["name"] != prior_item.get("name"):
                            raise ValueError("PMA Responses call history differs from visible history")
                        items.append({"type": "function_call", "call_id": call_id,
                                      "name": fn["name"], "arguments": fn["arguments"]})
                        emitted_calls.add(call_id)
                    else:
                        raise ValueError("unsupported PMA opaque Responses item")
                if emitted_calls != set(current_calls) or (text_now and not emitted_message):
                    raise ValueError("PMA Responses visible history is incomplete")
                continue
            if row.get("reasoning_content") or row.get("thinking_blocks"):
                raise ValueError("foreign provider reasoning cannot enter GPT history")
            content = row.get("content")
            if content:
                items.append({"role": "assistant", "content": _text(content)})
            for call in row.get("tool_calls") or []:
                if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
                    raise ValueError("PMA assistant tool call invalid")
                fn = call["function"]
                if not all(isinstance(value, str) and value for value in
                           (call.get("id"), fn.get("name"), fn.get("arguments"))):
                    raise ValueError("PMA assistant tool call identity invalid")
                items.append({"type": "function_call", "call_id": call["id"],
                              "name": fn["name"], "arguments": fn["arguments"]})
        else:
            raise ValueError("unsupported PMA history role")
    items.append({"role": "user", "content": prompt})
    return items


def _tools(schema: list[dict] | None) -> list[dict] | None:
    if not schema:
        return None
    result = []
    for item in schema:
        if not isinstance(item, dict) or item.get("type") != "function":
            raise ValueError("unsupported PMA tool schema")
        fn = item.get("function")
        if not isinstance(fn, dict) or not isinstance(fn.get("name"), str):
            raise ValueError("invalid PMA function schema")
        result.append({"type": "function", "name": fn["name"],
                       "description": fn.get("description", ""),
                       "parameters": fn["parameters"], "strict": False})
    return result


class ResponsesMemoryLLM(BaseLLM):
    """Stateless GPT transport; all function and encrypted-reasoning items replay."""

    def __init__(self, profile: dict):
        from openai import AsyncOpenAI

        self.model = profile["model"]
        # Upstream MemoryEnabledTerminus2.save_memory reads this LiteLLM
        # compatibility field when persisting the final trajectory.
        self._model_name = "openai/" + self.model
        self.max_tokens = profile["max_tokens"]
        self.context_window = profile["model_context_window"]
        self.effort = profile["reasoning_effort"]
        self.request_public_summary = profile.get("request_public_summary", False)
        if type(self.request_public_summary) is not bool:
            raise ValueError("request_public_summary must be a boolean")
        self.client = AsyncOpenAI(
            api_key=profile["apikey"], base_url=profile["apibase"],
            timeout=profile["read_timeout"], max_retries=profile["max_retries"],
            default_headers=profile.get("http_headers"))
        self.last_effective_request: dict | None = None
        self.last_visible_response: dict | None = None

    def get_model_context_limit(self) -> int:
        return self.context_window

    def get_model_output_limit(self) -> int | None:
        return self.max_tokens

    async def call(self, prompt: str, *, system: str, tools=None,
                   message_history=None) -> LLMResponse:
        if not isinstance(system, str):
            raise ValueError("PMA system prompt must be text")
        request = {"model": self.model, "instructions": system,
                   "input": response_input(message_history or [], prompt),
                   "max_output_tokens": self.max_tokens,
                   "reasoning": {"effort": self.effort}, "store": False}
        if self.request_public_summary:
            request["reasoning"]["summary"] = "auto"
        converted_tools = _tools(tools)
        if converted_tools:
            request["tools"] = converted_tools
            request["tool_choice"] = {"type": "allowed_tools", "mode": "auto",
                                      "tools": [{"type": "function", "name": tool["name"]}
                                                for tool in converted_tools]}
        else:
            request["tool_choice"] = "none"
        self.last_effective_request = request
        result = await self.client.responses.create(**request)
        body = result.model_dump(exclude_none=True)
        self.last_visible_response = {"id": body.get("id"), "model": body.get("model"),
                                      "status": body.get("status"), "usage": body.get("usage")}
        if body.get("model") != self.model:
            raise RuntimeError("PMA provider returned a different model identity")
        if body.get("status") != "completed":
            raise RuntimeError("PMA Responses request did not complete")
        output = body.get("output")
        if not isinstance(output, list):
            raise RuntimeError("PMA Responses output missing")
        # Keep only structural types in transport diagnostics. A completed
        # provider response can contain an item this adapter cannot replay;
        # naming its type is necessary to diagnose that boundary safely.
        self.last_visible_response["output_item_types"] = [
            item.get("type") if isinstance(item, dict) else type(item).__name__
            for item in output
        ]
        text, calls, ids = [], [], set()
        for item in output:
            kind = item.get("type")
            if kind == "message":
                for block in item.get("content") or []:
                    if block.get("type") == "output_text":
                        text.append(block.get("text", ""))
            elif kind == "function_call":
                call_id, name, arguments = (item.get("call_id"), item.get("name"),
                                            item.get("arguments"))
                if (not isinstance(call_id, str) or not call_id or call_id in ids or
                        not isinstance(name, str) or not name or
                        not isinstance(arguments, str)):
                    raise RuntimeError("PMA Responses function call invalid")
                ids.add(call_id)
                calls.append(SimpleNamespace(id=call_id,
                    function=SimpleNamespace(name=name, arguments=json.loads(arguments))))
            elif kind != "reasoning":
                raise RuntimeError(f"unsupported PMA Responses output item: {kind!r}")
        # The pinned worker stages the vendor Harbor dataclass, whose
        # constructor only accepts content/reasoning/usage and optional
        # tool_calls. Metadata is attached after construction so both the
        # staged type and the installed SDK-facing type behave identically.
        response = LLMResponse(content="\n".join(text))
        response.tool_calls = calls
        response.model_name = self.model
        response.response_id = body.get("id")
        response.openai_output_items = output
        response.actual_model = body["model"]
        response.provider_usage = body.get("usage")
        response.public_reasoning_summary = public_reasoning_summary(
            output, requested=self.request_public_summary)
        return response
