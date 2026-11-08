"""Responses-API transport for the frozen read-context PMA candidate.

Only the provider envelope is adapted. The PMA prompts, tool execution,
knowledge bank, history trimming and reminder parser remain in their owners.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from harbor.llms.base import BaseLLM, LLMResponse


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
                items.extend(opaque)
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
        self.max_tokens = profile["max_tokens"]
        self.context_window = profile["model_context_window"]
        self.effort = profile["reasoning_effort"]
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
        converted_tools = _tools(tools)
        if converted_tools:
            request["tools"] = converted_tools
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
                raise RuntimeError("unsupported PMA Responses output item")
        response = LLMResponse(content="\n".join(text), model_name=self.model,
                               response_id=body.get("id"))
        response.tool_calls = calls
        response.openai_output_items = output
        response.actual_model = body["model"]
        response.provider_usage = body.get("usage")
        return response
