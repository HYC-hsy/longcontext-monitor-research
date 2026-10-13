"""Offline tests: real upstream object and MemoryAgent, scripted LiteLLM I/O."""

import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from types import SimpleNamespace

# Offline tests must not let LiteLLM fetch its optional price metadata.
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from harbor.llms.base import LLMResponse
from memory_agent.utils.visualize import visualize_memory, visualize_memory_trajectory

from episode import DisabledActorLLM, PMAEpisode, construct_upstream
from event_spool import EventClient, EventDispatcher


class EpisodeTests(unittest.TestCase):
    def test_original_lifecycle_and_duplicate_suppression(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            agent = construct_upstream(root / "agent")
            calls = []

            async def fake_memory_call(*, prompt, system, tools=None):
                calls.append({"prompt": prompt, "system": system,
                              "tools": bool(tools)})
                if tools:
                    return LLMResponse(content="", tool_calls=[])
                if len(calls) == 2:
                    return LLMResponse(content="<context_for_action>Remember X</context_for_action>")
                return LLMResponse(content="<no_intervention/>")

            agent._memory_llm.call = fake_memory_call
            episode = PMAEpisode(agent, run_id="r", task_id="t", archive=root / "private")

            def event(kind, sequence, **fields):
                return {"kind": kind, "sequence": sequence,
                        "event_id": f"e{sequence}", "run_id": "r", "task_id": "t", **fields}

            async def run():
                start = event("task_start", 1, initial_user_content="Original public GA input")
                self.assertTrue((await episode.handle(start))["triggered"])
                self.assertEqual(await episode.handle(start), await episode.handle(start))
                before = await episode.handle(event("before_actor_call", 2, actor_attempt=1))
                self.assertIn("Remember X", before["reminder"])
                self.assertEqual(before["delivery"], "returned_not_confirmed_in_ga_request")
                observed = await episode.handle(event(
                    "actor_step", 3, actor_attempt=1, step_status="normal",
                    commands=["tool A", "tool B"], observation="two public results"))
                self.assertEqual(observed["step_count"], 2)
                self.assertEqual((await episode.handle(event(
                    "before_actor_call", 4, actor_attempt=2)))["status"], "silent")
                skipped = await episode.handle(event(
                    "actor_step", 5, actor_attempt=2, step_status="parse_error"))
                self.assertEqual(skipped["status"], "skipped")
                self.assertEqual((await episode.handle(event(
                    "before_actor_call", 6, actor_attempt=3)))["actor_attempt"], 3)
                await episode.handle(event("actor_step", 7, actor_attempt=3,
                                           step_status="completed"))
                self.assertEqual((await episode.handle(event(
                    "task_end", 8, terminal="CURRENT_TASK_DONE")))["status"], "saved")

            asyncio.run(run())
            self.assertEqual(len(calls), 4)  # Two real PMA phases at each trigger.
            self.assertEqual([x["tools"] for x in calls], [True, False, True, False])
            self.assertEqual(agent._accumulated_observations[1]["commands"], ["tool A", "tool B"])
            self.assertEqual(agent._accumulated_observations[1]["step"], 2)
            self.assertIn("two public results", calls[2]["prompt"])
            self.assertEqual(agent._llm.calls, 0)
            self.assertIsInstance(agent._llm, DisabledActorLLM)
            self.assertTrue((root / "private" / "memory.json").is_file())
            self.assertTrue((root / "private" / "trajectory_memory.json").is_file())
            self.assertIsNotNone(visualize_memory(root / "private" / "memory.json"))
            self.assertIsNotNone(visualize_memory_trajectory(
                root / "private" / "trajectory_memory.json"))

    def test_actor_never_usable(self):
        with TemporaryDirectory() as directory:
            agent = construct_upstream(Path(directory))
            with self.assertRaisesRegex(RuntimeError, "actor is disabled"):
                asyncio.run(agent._llm.call("must fail"))

    def test_file_event_bridge_keeps_private_bank_outside_shared_spool(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            requests, responses = root / "shared" / "requests", root / "shared" / "responses"
            requests.mkdir(parents=True)
            responses.mkdir()
            agent = construct_upstream(root / "agent")
            calls = []

            async def fake_memory_call(*, prompt, system, tools=None):
                calls.append(bool(tools))
                return LLMResponse(content="<no_intervention/>", tool_calls=[])

            agent._memory_llm.call = fake_memory_call
            episode = PMAEpisode(agent, run_id="r", task_id="t", archive=root / "host_private")
            dispatcher = EventDispatcher(episode, requests, responses)
            client = EventClient(requests, responses, "r", "t",
                                 deadline_monotonic=time.monotonic() + 5)

            async def run():
                pending = asyncio.create_task(asyncio.to_thread(
                    client.exchange, "task_start", initial_user_content="GA public input"))
                while not pending.done():
                    await dispatcher.serve_once()
                    await asyncio.sleep(.01)
                self.assertEqual((await pending)["status"], "started")
                self.assertEqual(await dispatcher.serve_once(), 0)

            asyncio.run(run())
            self.assertEqual(calls, [True, False])
            self.assertFalse((root / "shared" / "host_private").exists())
            self.assertFalse(any("memory" in p.name for p in requests.iterdir()))
            receipt = json.loads(next(responses.iterdir()).read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "ok")
            self.assertNotIn("memory_stats", receipt["result"])

    def test_unmodified_upstream_actor_loop_reference_first_two_steps(self):
        """Reference runs upstream _run_agent_loop, not the GA event adapter."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            agent = construct_upstream(root / "reference")
            memory_requests = []

            async def fake_memory_call(*, prompt, system, tools=None):
                memory_requests.append((bool(tools), prompt))
                if tools:
                    return LLMResponse(content="", tool_calls=[])
                if len(memory_requests) == 2:
                    return LLMResponse(content="<context_for_action>Remember X</context_for_action>")
                return LLMResponse(content="<no_intervention/>")

            agent._memory_llm.call = fake_memory_call
            agent._context = SimpleNamespace()
            agent._max_episodes = 2
            agent._enable_summarize = False
            agent._session = SimpleNamespace(is_session_alive=lambda: asyncio.sleep(0, result=True))
            agent._setup_episode_logging = lambda *a: None
            agent._record_asciinema_marker = lambda *a: None
            agent._record_step_full = lambda *a, **k: None
            agent._record_step = lambda *a, **k: None
            agent._dump_trajectory = lambda: None
            seen_actor_prompts = []

            class FakeChat:
                total_input_tokens = 0
                total_output_tokens = 0
                total_cache_tokens = 0
                total_cost = 0

                async def chat(self, prompt, logging_path=None, **kwargs):
                    seen_actor_prompts.append(prompt)
                    return LLMResponse(content="actor")

            actor_calls = 0

            async def fake_actor_interaction(chat, prompt, *args):
                nonlocal actor_calls
                await chat.chat(prompt)
                actor_calls += 1
                if actor_calls == 1:
                    return (["tool A", "tool B"], False, "", None, None,
                            LLMResponse(content="actor"))
                return ([], False, "ERROR: parse", None, None,
                        LLMResponse(content="bad actor format"))

            agent._handle_llm_interaction = fake_actor_interaction
            agent._execute_commands = lambda commands, session: asyncio.sleep(
                0, result=(False, "two public results"))
            asyncio.run(agent._run_agent_loop("Original public GA input", FakeChat()))
            self.assertEqual(actor_calls, 2)
            self.assertIn("Remember X", seen_actor_prompts[0])
            self.assertEqual(seen_actor_prompts[1], "two public results")
            self.assertEqual([entry["step"] for entry in agent._accumulated_observations],
                             [1, 2])
            self.assertEqual(agent._accumulated_observations[1]["commands"],
                             ["tool A", "tool B"])
            self.assertEqual(len(memory_requests), 4)
            self.assertEqual(agent._llm.calls, 0)


if __name__ == "__main__":
    unittest.main()
