"""Offline tests: real upstream object and MemoryAgent, scripted LiteLLM I/O."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

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


if __name__ == "__main__":
    unittest.main()
