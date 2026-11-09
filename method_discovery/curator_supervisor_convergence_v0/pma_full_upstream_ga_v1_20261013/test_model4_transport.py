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
from episode import PMAEpisode, construct_upstream
from worker_main import install_transport_audit
from memory_agent.memory.ga_context_history import (
    _history_bytes, _msgs_claude2oai, compress_history_tags)


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
        for model in ("gpt-6-sol", "gpt-6-astra"):
            with self.subTest(model=model):
                name, actual = load_profile(json.dumps({"pma_model": self.profile(model)}).encode(),
                                            READ_CONTEXT)
                self.assertEqual((name, actual["model"]), ("pma_model", model))
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

    def test_compression_changes_actual_responses_input_and_budget(self):
        long_text = "<tool_result>" + "A" * 4000 + "</tool_result>"
        opaque = [{"type": "reasoning", "encrypted_content": "opaque-private"},
                  {"type": "message", "content": [{"type": "output_text",
                                                      "text": long_text}]}]
        old = {"role": "assistant", "content": [{"type": "text", "text": long_text}],
               "_openai_output_items": opaque}
        history = [old, {"role": "user", "content": [{"type": "text", "text": "next"}]}]
        without_mirror = [{key: value for key, value in old.items()
                           if key != "_openai_output_items"}, history[1]]
        self.assertLess(_history_bytes(history) - _history_bytes(without_mirror), 200)
        before = _history_bytes(history)
        compress_history_tags(history, keep_recent=1, force=True)
        self.assertLess(_history_bytes(history), before)
        converted = _msgs_claude2oai([history[0]])[0]
        converted["_openai_output_items"] = opaque
        items = response_input([converted], "Continue.")
        actual = json.dumps(items)
        self.assertIn("[Truncated]", actual)
        self.assertNotIn("A" * 4000, actual)
        self.assertIn("opaque-private", actual)
        llm = ResponsesMemoryLLM(self.profile())
        class FakeResponses:
            async def create(self, **_):
                return SimpleNamespace(model_dump=lambda **__: {
                    "model": "gpt-6.1-sol", "status": "completed", "output": [{
                        "type": "message", "content": [{"type": "output_text",
                                                     "text": "<no_intervention/>"}]}]})
        llm.client.responses = FakeResponses()
        asyncio.run(llm.call("Continue.", system="system", message_history=[converted]))
        sent = json.dumps(llm.last_effective_request)
        self.assertIn("[Truncated]", sent)
        self.assertNotIn("A" * 4000, sent)

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
        self.assertEqual(calls[0]["tool_choice"], {"type": "allowed_tools",
            "mode": "auto", "tools": [{"type": "function", "name": "memory_add"}]})
        self.assertNotIn("temperature", calls[0])

    def test_repeated_provider_call_id_across_responses_keeps_history_paired(self):
        llm = ResponsesMemoryLLM(self.profile("gpt-6-sol"))
        sent = []
        class FakeResponses:
            async def create(self, **kwargs):
                sent.append(kwargs)
                return SimpleNamespace(model_dump=lambda **_: {
                    "id": "resp_0", "model": "gpt-6-sol", "status": "completed",
                    "output": [{"type": "reasoning", "encrypted_content": "opaque"},
                               {"type": "function_call", "call_id": "sg_call_1",
                                "name": "memory_add", "arguments": '{"content":"note"}'}]})
        llm.client.responses = FakeResponses()
        first = asyncio.run(llm.call("task", system="system"))
        first_id = first.tool_calls[0].id
        self.assertEqual(first_id, "sg_call_1")
        first_history = [{"role": "assistant", "tool_calls": [{"id": first_id,
            "function": {"name": "memory_add", "arguments": '{"content":"note"}'}}],
            "_openai_output_items": first.openai_output_items},
            {"role": "tool", "tool_call_id": first_id, "content": "saved"}]
        second = asyncio.run(llm.call("next", system="system", message_history=first_history))
        second_id = second.tool_calls[0].id
        self.assertNotEqual(second_id, first_id)
        self.assertEqual(llm.last_visible_response["call_id_aliases"], [
            {"provider_call_id": "sg_call_1", "history_call_id": second_id}])
        self.assertEqual(second.openai_output_items[-1]["call_id"], second_id)
        self.assertEqual(sent[-1]["input"][-3]["call_id"], first_id)
        combined = first_history + [{"role": "assistant", "tool_calls": [{
            "id": second_id, "function": {"name": "memory_add",
            "arguments": '{"content":"note"}'}}],
            "_openai_output_items": second.openai_output_items},
            {"role": "tool", "tool_call_id": second_id, "content": "saved"}]
        items = response_input(combined, "continue")
        self.assertEqual([item["call_id"] for item in items
                          if item.get("type") == "function_call"], [first_id, second_id])
        self.assertEqual([item["call_id"] for item in items
                          if item.get("type") == "function_call_output"], [first_id, second_id])

    def test_repeated_provider_call_id_within_one_response_still_fails(self):
        llm = ResponsesMemoryLLM(self.profile("gpt-6-sol"))
        class FakeResponses:
            async def create(self, **_):
                return SimpleNamespace(model_dump=lambda **__: {
                    "model": "gpt-6-sol", "status": "completed", "output": [
                        {"type": "function_call", "call_id": "same", "name": "memory_add",
                         "arguments": '{"content":"one"}'},
                        {"type": "function_call", "call_id": "same", "name": "memory_add",
                         "arguments": '{"content":"two"}'}]})
        llm.client.responses = FakeResponses()
        with self.assertRaisesRegex(RuntimeError, "function call invalid"):
            asyncio.run(llm.call("task", system="system"))

    def test_repeated_call_id_alias_is_written_to_private_transport_audit(self):
        llm = ResponsesMemoryLLM(self.profile("gpt-6-sol"))
        class FakeResponses:
            async def create(self, **_):
                return SimpleNamespace(model_dump=lambda **__: {
                    "id": "resp_0", "model": "gpt-6-sol", "status": "completed",
                    "output": [{"type": "function_call", "call_id": "sg_call_1",
                                "name": "memory_add", "arguments": '{"content":"note"}'}]})
        llm.client.responses = FakeResponses()
        agent = SimpleNamespace(_memory_llm=llm,
                                _memory_agent=SimpleNamespace(_history_transforms=[], _step=8),
                                _research_candidate=READ_CONTEXT)
        with TemporaryDirectory() as directory:
            archive = Path(directory)
            install_transport_audit(agent, archive)
            asyncio.run(llm.call(prompt="first", system="system"))
            asyncio.run(llm.call(prompt="second", system="system"))
            rows = [json.loads(line) for line in
                    (archive / "memory_transport.jsonl").read_text().splitlines()]
            self.assertEqual(rows[0]["call_id_aliases"], [])
            self.assertEqual(rows[1]["call_id_aliases"][0]["provider_call_id"], "sg_call_1")
            self.assertNotEqual(rows[1]["call_id_aliases"][0]["history_call_id"], "sg_call_1")

    def test_returned_model_is_recorded_without_rejecting_response(self):
        llm = ResponsesMemoryLLM(self.profile("gpt-6-sol"))
        returned = ["gpt-6-astra", None]
        class FakeResponses:
            async def create(self, **_):
                model = returned.pop(0)
                return SimpleNamespace(model_dump=lambda **__: {
                    "id": "response-test", "model": model, "status": "completed",
                    "output": [{"type": "message", "content": [
                        {"type": "output_text", "text": "<no_intervention/>"}]}]})
        llm.client.responses = FakeResponses()
        for expected in ("gpt-6-astra", None):
            with self.subTest(returned_model=expected):
                response = asyncio.run(llm.call("task", system="system"))
                self.assertEqual(response.content, "<no_intervention/>")
                self.assertEqual(response.actual_model, expected)
                self.assertEqual(llm.last_effective_request["model"], "gpt-6-sol")
                self.assertEqual(llm.last_visible_response["model"], expected)
                self.assertEqual(llm.last_visible_response["id"], "response-test")
        self.assertFalse(returned)

    def test_transport_audit_keeps_requested_and_returned_models(self):
        llm = ResponsesMemoryLLM(self.profile("gpt-6-sol"))
        class FakeResponses:
            async def create(self, **_):
                return SimpleNamespace(model_dump=lambda **__: {
                    "id": "different-model-response", "model": "gpt-6-astra",
                    "status": "completed", "output": [{"type": "message",
                    "content": [{"type": "output_text", "text": "<no_intervention/>"}]}]})
        llm.client.responses = FakeResponses()
        agent = SimpleNamespace(_memory_llm=llm,
                                _memory_agent=SimpleNamespace(_history_transforms=[], _step=8),
                                _research_candidate=READ_CONTEXT)
        with TemporaryDirectory() as directory:
            archive = Path(directory)
            install_transport_audit(agent, archive)
            response = asyncio.run(llm.call(prompt="task", system="system"))
            self.assertEqual(response.actual_model, "gpt-6-astra")
            transport = json.loads((archive / "memory_transport.jsonl").read_text())
            self.assertEqual(transport["status"], "complete")
            self.assertEqual(transport["requested_model"], "gpt-6-sol")
            self.assertEqual(transport["returned_model"], "gpt-6-astra")
            self.assertEqual(transport["response_id"], "different-model-response")
            saved = json.loads((archive / "memory_response.jsonl").read_text())
            self.assertEqual(saved["actual_model"], "gpt-6-astra")

    def test_unknown_response_item_reports_type_without_content(self):
        llm = ResponsesMemoryLLM(self.profile())
        class FakeResponses:
            async def create(self, **_):
                return SimpleNamespace(model_dump=lambda **__: {
                    "model": "gpt-6.1-sol", "status": "completed",
                    "output": [{"type": "new_item", "secret": "not-for-errors"}]})
        llm.client.responses = FakeResponses()
        with self.assertRaisesRegex(RuntimeError, "new_item") as caught:
            asyncio.run(llm.call("task", system="system"))
        self.assertNotIn("not-for-errors", str(caught.exception))
        self.assertEqual(llm.last_visible_response["output_item_types"], ["new_item"])

    def test_candidate_constructor_model_binding(self):
        for model in ("claude-opus-4-8", "claude-opus-5", "claude-fable-5",
                      "gpt-6.1-sol", "gpt-6-sol", "gpt-6-astra"):
            if model.startswith("gpt-"):
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
                if model.startswith("gpt-"):
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
                response = await llm.call("task", system="system")
                await llm.call("task", system="system", tools=[{
                    "type": "function", "function": {"name": "memory_read",
                    "description": "read", "parameters": {"type": "object",
                    "properties": {"bank_id": {"type": "string"}}}}}])
                return response
        response = asyncio.run(run())
        self.assertEqual(response.content, "<no_intervention/>")
        self.assertEqual(len(recorded), 2)
        self.assertEqual(recorded[0]["input"], [{"role": "user", "content": "task"}])
        self.assertEqual(recorded[0]["reasoning"], {"effort": "high"})
        self.assertFalse(recorded[0]["store"])
        self.assertEqual(recorded[0]["tool_choice"], "none")
        self.assertEqual(recorded[1]["tool_choice"], {"type": "allowed_tools",
            "mode": "auto", "tools": [{"type": "function", "name": "memory_read"}]})

    def test_staged_harbor_full_p1_p2_success(self):
        from harbor.llms.base import LLMResponse
        self.assertIn("content", LLMResponse.__dataclass_fields__)
        async def run():
            with TemporaryDirectory() as directory:
                agent = construct_upstream(Path(directory), memory_profile=self.profile(),
                                           research_candidate=READ_CONTEXT)
                memory = agent._memory_agent
                memory.set_phase1_context(task="task description", trajectory="")
                responses = [
                    {"model": "gpt-6.1-sol", "status": "completed", "id": "p1",
                     "output": [{"type": "function_call", "call_id": "call_1",
                                 "name": "memory_add", "arguments": '{"content":"remember this"}'}]},
                    {"model": "gpt-6.1-sol", "status": "completed", "id": "p2",
                     "output": [{"type": "message", "content": [
                         {"type": "output_text", "text": "<no_intervention/>"}]}]},
                ]
                class FakeResponses:
                    async def create(self, **_):
                        return SimpleNamespace(model_dump=lambda **__: responses.pop(0))
                agent._memory_llm.client.responses = FakeResponses()
                result = await memory.process("task description", step_count=0)
                self.assertEqual(len(result.operations), 1)
                self.assertTrue(result.operations[0].success)
                self.assertFalse(result.should_inject)
                self.assertFalse(responses)
                saved = Path(directory) / "memory.json"
                agent.save_memory(str(saved))
                self.assertTrue(saved.is_file())
                trajectory = json.loads((Path(directory) / "trajectory_memory.json").read_text())
                self.assertEqual(trajectory["memory_model_name"], "openai/gpt-6.1-sol")
        asyncio.run(run())

    def test_gpt_episode_task_end_persists_both_artifacts(self):
        async def run():
            with TemporaryDirectory() as directory:
                root = Path(directory)
                agent = construct_upstream(root / "upstream", memory_profile=self.profile(),
                                           research_candidate=READ_CONTEXT)
                outputs = [
                    {"model": "gpt-6.1-sol", "status": "completed", "id": "p1",
                     "output": [{"type": "message", "content": [{
                         "type": "output_text", "text": "No memory update."}]}]},
                    {"model": "gpt-6.1-sol", "status": "completed", "id": "p2",
                     "output": [{"type": "message", "content": [{
                         "type": "output_text", "text": "<no_intervention/>"}]}]},
                ]
                class FakeResponses:
                    async def create(self, **_):
                        return SimpleNamespace(model_dump=lambda **__: outputs.pop(0))
                agent._memory_llm.client.responses = FakeResponses()
                episode = PMAEpisode(agent, run_id="synthetic", task_id="synthetic",
                                     archive=root / "archive")
                common = {"run_id": "synthetic", "task_id": "synthetic"}
                started = await episode.handle({**common, "kind": "task_start",
                    "event_id": "start", "sequence": 1, "initial_user_content": "task"})
                self.assertEqual(started["status"], "started")
                ended = await episode.handle({**common, "kind": "task_end",
                    "event_id": "end", "sequence": 2,
                    "terminal": {"result": "CURRENT_TASK_DONE"}})
                self.assertEqual(ended["status"], "saved")
                self.assertTrue(episode.ended)
                self.assertFalse(outputs)
                self.assertTrue((root / "archive" / "memory.json").is_file())
                self.assertTrue((root / "archive" / "trajectory_memory.json").is_file())
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
