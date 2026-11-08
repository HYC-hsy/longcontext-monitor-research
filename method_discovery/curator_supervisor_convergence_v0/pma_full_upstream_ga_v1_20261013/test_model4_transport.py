"""Zero-model checks for the four-model PMA transport binding."""

import asyncio
import httpx
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from pma_model_profile import load_profile, READ_CONTEXT
from responses_memory_llm import ResponsesMemoryLLM, response_input
from episode import construct_upstream


class Model4TransportTests(unittest.TestCase):
    def profile(self, model="gpt-6.1-sol"):
        return {"provider": "openai", "api_mode": "responses", "model": model,
                "apibase": "https://example.invalid/v1", "apikey": "test-only",
                "store": False, "reasoning_effort": "high", "max_tokens": 8192,
                "model_context_window": 200000, "read_timeout": 300,
                "max_retries": 2}

    def test_profile_binding_and_default_isolation(self):
        profile = self.profile()
        name, actual = load_profile(json.dumps({"pma_model": profile}).encode(), READ_CONTEXT)
        self.assertEqual((name, actual["model"]), ("pma_model", "gpt-6.1-sol"))
        with self.assertRaises(ValueError):
            load_profile(json.dumps({"pma_model": profile}).encode(), "U")
        for key, value in (("temperature", 0), ("store", True),
                           ("api_mode", "messages")):
            bad = dict(profile, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                load_profile(json.dumps({"pma_model": bad}).encode(), READ_CONTEXT)

    def test_ordered_history_and_opaque_reasoning(self):
        opaque = [{"type": "reasoning", "encrypted_content": "private-test"},
                  {"type": "function_call", "call_id": "c1", "name": "memory_read",
                   "arguments": '{"bank_id":"knowledge"}'}]
        history = [{"role": "user", "content": [{"type": "text", "text": "task"}]},
                   {"role": "assistant", "tool_calls": [{"id": "c1", "type": "function",
                       "function": {"name": "memory_read", "arguments": '{"bank_id":"knowledge"}'}}],
                    "_openai_output_items": opaque},
                   {"role": "tool", "tool_call_id": "c1", "content": "bank data"}]
        items = response_input(history, "Continue.")
        self.assertEqual([item.get("type", item.get("role")) for item in items],
                         ["user", "reasoning", "function_call", "function_call_output", "user"])
        self.assertEqual(items[-2]["call_id"], "c1")
        self.assertEqual(items[-2]["output"], "bank data")

    def test_request_and_native_tool_response(self):
        llm = ResponsesMemoryLLM(self.profile())
        calls = []
        class FakeResponses:
            async def create(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(model_dump=lambda **_: {
                    "model": "gpt-6.1-sol", "status": "completed",
                    "usage": {"input_tokens": 10, "output_tokens": 4},
                    "output": [{"type": "reasoning", "encrypted_content": "opaque"},
                               {"type": "function_call", "call_id": "c2",
                                "name": "memory_add", "arguments": '{"content":"note"}'}]})
        llm.client.responses = FakeResponses()
        response = asyncio.run(llm.call("task", system="system", tools=[{
            "type": "function", "function": {"name": "memory_add", "description": "add",
            "parameters": {"type": "object", "properties": {"content": {"type": "string"}}}}}]))
        self.assertEqual(response.tool_calls[0].id, "c2")
        self.assertEqual(response.tool_calls[0].function.arguments, {"content": "note"})
        self.assertEqual(response.provider_usage["input_tokens"], 10)
        self.assertEqual(calls[0]["model"], "gpt-6.1-sol")
        self.assertFalse(calls[0]["store"])
        self.assertEqual(calls[0]["tools"][0]["name"], "memory_add")
        self.assertNotIn("temperature", calls[0])

    def test_candidate_constructor_model_binding(self):
        for model in ("claude-opus-4-8", "claude-opus-5", "claude-fable-5", "gpt-6.1-sol"):
            if model == "gpt-6.1-sol":
                profile = self.profile()
            else:
                profile = {"provider": "anthropic", "api_mode": "messages", "model": model,
                           "apibase": "https://example.invalid/v1", "apikey": "test-only",
                           "thinking_type": "adaptive", "temperature": 1,
                           "reasoning_effort": "high", "max_tokens": 8192,
                           "read_timeout": 300, "max_retries": 2}
            with self.subTest(model=model), TemporaryDirectory() as directory:
                agent = construct_upstream(Path(directory), memory_profile=profile,
                                           research_candidate=READ_CONTEXT)
                self.assertEqual(agent._research_candidate, READ_CONTEXT)
                self.assertIn("ReadContextPredictiveMemoryAgent",
                              type(agent._memory_agent).__name__)
                if model == "gpt-6.1-sol":
                    self.assertIsInstance(agent._memory_llm, ResponsesMemoryLLM)

    def test_installed_openai_sdk_serializes_responses_request(self):
        from openai import AsyncOpenAI
        recorded = []
        def handler(request):
            recorded.append(json.loads(request.content))
            return httpx.Response(200, json={
                "id": "resp_test", "object": "response", "created_at": 1,
                "model": "gpt-6.1-sol", "status": "completed", "output": [{
                    "type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": "<no_intervention/>",
                                 "annotations": []}]}],
                "usage": {"input_tokens": 12, "output_tokens": 3,
                          "total_tokens": 15}})
        async def run():
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as http_client:
                llm = ResponsesMemoryLLM(self.profile())
                llm.client = AsyncOpenAI(api_key="test-only",
                    base_url="https://example.invalid/v1", http_client=http_client,
                    max_retries=0)
                return await llm.call("task", system="system")
        response = asyncio.run(run())
        self.assertEqual(response.content, "<no_intervention/>")
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["input"], [{"role": "user", "content": "task"}])
        self.assertEqual(recorded[0]["reasoning"], {"effort": "high"})
        self.assertFalse(recorded[0]["store"])


if __name__ == "__main__":
    unittest.main()
