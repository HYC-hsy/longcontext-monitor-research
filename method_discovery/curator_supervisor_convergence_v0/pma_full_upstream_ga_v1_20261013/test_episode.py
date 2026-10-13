"""Offline tests: real upstream object and MemoryAgent, scripted LiteLLM I/O."""

import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from types import SimpleNamespace
import sys
from unittest.mock import patch

# Offline tests must not let LiteLLM fetch its optional price metadata.
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "GenericAgent-main"))

from harbor.llms.base import LLMResponse
from harbor.llms.lite_llm import LiteLLM
from memory_agent.utils.visualize import visualize_memory, visualize_memory_trajectory

from episode import DisabledActorLLM, PMAEpisode, construct_upstream
from event_spool import EventClient, EventDispatcher
from pma_upstream_bridge import UpstreamPMAClient
import worker_main
import offline_launcher


class EpisodeTests(unittest.TestCase):
    def test_existing_opus48_profile_uses_upstream_litellm_boundary(self):
        profile = dict(provider="anthropic", api_mode="messages",
                       model="claude-opus-4-8", thinking_type="adaptive",
                       reasoning_effort="high", temperature=1, max_tokens=8192,
                       read_timeout=300, apibase="https://offline.invalid/v1",
                       apikey="offline-only")
        seen = []

        async def fake_call(self, prompt, **kwargs):
            seen.append(dict(prompt=prompt, **kwargs))
            return LLMResponse(content="<no_intervention/>")

        with TemporaryDirectory() as directory, patch.object(LiteLLM, "call", fake_call):
            agent = construct_upstream(Path(directory) / "agent", memory_profile=profile)
            self.assertEqual(agent._memory_llm._model_name, "anthropic/claude-opus-4-8")
            self.assertEqual(agent._memory_llm._temperature, 1)
            self.assertEqual(agent._memory_llm._reasoning_effort, "high")
            asyncio.run(agent._memory_llm.call(prompt="public", system="upstream"))
        self.assertEqual(seen[0]["max_tokens"], 8192)
        self.assertEqual(seen[0]["thinking"], {"type": "adaptive"})
        self.assertEqual(seen[0]["timeout"], 300)
        self.assertEqual(DisabledActorLLM.calls, 0)

    def test_launcher_docker_inspect_failure_keeps_terminal_and_cleanup(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "fresh_run"
            for name in ("archive", "bundle/source", "public_task", "control"):
                (root / name).mkdir(parents=True, exist_ok=True)
            (root / "bundle/isolation.compose.json").write_text("{}", encoding="utf-8")
            class FakeHarbor:
                returncode = None
                def poll(self):
                    return self.returncode
                def kill(self):
                    self.returncode = -9
                def wait(self, timeout):
                    return self.returncode
            fake = FakeHarbor()
            args = SimpleNamespace(run_root=str(root), condition="A", timeout_sec=5,
                runtime_root=directory, harbor_exe=sys.executable,
                bench_root=directory, run_id="fixture", task="db-wal-recovery",
                python_home="python", task_profile="fixture")
            with (patch.object(offline_launcher, "prepare", return_value={
                    "image_id": "fixture-image", "ga_bundle_tree_sha256": "fixture-tree"}),
                  patch.object(offline_launcher, "_offline_gateway"),
                  patch.object(offline_launcher.subprocess, "Popen", return_value=fake),
                  patch.object(offline_launcher, "capture_mounts",
                               side_effect=[RuntimeError("Docker inspect failed"), []]),
                  patch.object(offline_launcher, "clean_owned_containers", return_value=[])):
                result = offline_launcher.run_offline(args)
            self.assertEqual(result["primary_failure"]["type"], "RuntimeError")
            self.assertTrue(result["cleanup_confirmed"])
            self.assertFalse(result["integration_ok"])
            self.assertEqual(json.loads((root / "archive/offline_result.json").read_text())
                             ["primary_failure"]["message"], "Docker inspect failed")

    def test_original_lifecycle_and_duplicate_suppression(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            agent = construct_upstream(root / "agent")
            self.assertEqual(agent._memory_llm._model_name,
                             "openrouter/anthropic/claude-opus-4.6")
            self.assertEqual(agent._memory_llm._temperature, 0.3)
            self.assertTrue(agent._memory_agent.use_structured_tools)
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
                with self.assertRaisesRegex(ValueError, "non-monotonic actor attempt"):
                    await episode.handle(event("before_actor_call", 3, actor_attempt=2))
                observed = await episode.handle(event(
                    "actor_step", 3, actor_attempt=1, step_status="normal",
                    response="PUBLIC_DIAGNOSTIC: inspect both files",
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
            for call in calls[2:4]:
                self.assertIn("PUBLIC_DIAGNOSTIC: inspect both files", call["prompt"])
                self.assertIn("tool A", call["prompt"])
                self.assertIn("tool B", call["prompt"])
                self.assertIn("two public results", call["prompt"])
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

    def test_second_save_failure_never_marks_clean_end(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            agent = construct_upstream(root / "agent")
            agent._trigger.should_trigger = lambda step_count: (False, "fixture")
            episode = PMAEpisode(agent, run_id="r", task_id="t", archive=root / "private")
            original_save = agent.save_memory

            def fail_after_bank(path):
                agent._memory.save_to_file(Path(path))
                raise OSError("trajectory write failed")

            agent.save_memory = fail_after_bank

            async def run():
                await episode.handle({"kind": "task_start", "sequence": 1,
                                      "event_id": "a", "run_id": "r", "task_id": "t",
                                      "initial_user_content": "public"})
                with self.assertRaises(OSError):
                    await episode.handle({"kind": "task_end", "sequence": 2,
                                          "event_id": "b", "run_id": "r", "task_id": "t",
                                          "terminal": {"result": "CURRENT_TASK_DONE"}})

            asyncio.run(run())
            self.assertFalse(episode.ended)
            self.assertTrue(episode.finalization_attempted)
            self.assertFalse((root / "private" / "trajectory_memory.json").exists())
            self.assertIn("save_failed", (root / "private" / "events.jsonl").read_text())
            agent.save_memory = original_save

    def test_worker_deadline_cancels_inflight_without_late_receipt(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            requests, responses = root / "shared" / "requests", root / "shared" / "responses"
            requests.mkdir(parents=True)
            responses.mkdir()
            request = {"schema": "pma-ga-events-v1", "kind": "task_start",
                       "sequence": 1, "event_id": "first", "run_id": "r",
                       "task_id": "t", "initial_user_content": "public"}
            (requests / "first.json").write_text(json.dumps(request), encoding="utf-8")
            agent = construct_upstream(root / "agent")

            async def slow_memory(*, prompt, system, tools=None):
                await asyncio.sleep(5)
                return LLMResponse(content="<no_intervention/>", tool_calls=[])

            agent._memory_llm.call = slow_memory
            args = SimpleNamespace(private_root=str(root / "private"),
                                   requests=str(requests), responses=str(responses),
                                   run_id="r", task_id="t", fake_memory=False,
                                   deadline_epoch=time.time() + .25)
            with patch.object(worker_main, "construct_upstream", return_value=agent):
                asyncio.run(worker_main.serve(args))
            self.assertFalse((responses / "first.json").exists())
            exit_record = json.loads((root / "private" / "worker_exit.json").read_text())
            self.assertFalse(exit_record["task_end_saved"])
            self.assertEqual(exit_record["reason"], "stopped_or_deadline_in_flight_unknown")
            self.assertTrue((root / "private" / "archive" / "memory.json").is_file())

    def test_original_phase_errors_are_audited_without_changing_silence(self):
        for failed_phase in ("bank_management", "context_decision"):
            with self.subTest(failed_phase=failed_phase), TemporaryDirectory() as directory:
                root = Path(directory)
                agent = construct_upstream(root / "agent")

                async def fake_call(*, prompt, system, tools=None):
                    phase = "bank_management" if tools else "context_decision"
                    if phase == failed_phase:
                        raise RuntimeError("scripted upstream failure")
                    if tools:
                        return LLMResponse(content="", tool_calls=[])
                    return LLMResponse(content="<no_intervention/>")

                agent._memory_llm.call = fake_call
                episode = PMAEpisode(agent, run_id="r", task_id="t", archive=root / "private")
                worker_main.install_transport_audit(agent, episode.archive)

                async def run():
                    await episode.handle({"kind": "task_start", "sequence": 1,
                                          "event_id": "start", "run_id": "r", "task_id": "t",
                                          "initial_user_content": "public"})
                    return await episode.handle({"kind": "before_actor_call",
                                                 "sequence": 2, "event_id": "before",
                                                 "run_id": "r", "task_id": "t",
                                                 "actor_attempt": 1})

                self.assertEqual(asyncio.run(run())["status"], "silent")
                rows = [json.loads(line) for line in (episode.archive /
                        "memory_transport.jsonl").read_text().splitlines()]
                self.assertEqual([row["phase"] for row in rows],
                                 ["bank_management", "context_decision"])
                self.assertEqual(rows[0 if failed_phase == "bank_management" else 1]
                                 ["status"], "RuntimeError")

    def test_original_and_ga_initial_phase_failure_matrix(self):
        """Original loop is the reference; no adapter method drives it."""
        for failed_phase in (None, "bank_management", "context_decision"):
            with self.subTest(failed_phase=failed_phase), TemporaryDirectory() as directory:
                root = Path(directory)
                captured = {}
                agents = {}
                for arm in ("reference", "ga"):
                    agent = construct_upstream(root / arm)
                    agents[arm] = agent
                    captured[arm] = []

                    async def scripted(*, prompt, system, tools=None, arm=arm):
                        phase = "bank_management" if tools else "context_decision"
                        captured[arm].append((phase, prompt, system))
                        if phase == failed_phase:
                            raise RuntimeError("same scripted phase failure")
                        if tools:
                            return LLMResponse(content="", tool_calls=[])
                        return LLMResponse(content="<no_intervention/>")

                    agent._memory_llm.call = scripted
                reference = agents["reference"]
                reference._context = SimpleNamespace()
                reference._max_episodes = 0
                reference._enable_summarize = False
                reference._session = SimpleNamespace(is_session_alive=lambda: asyncio.sleep(0, result=True))
                class UnusedFakeChat:
                    async def chat(self, *args, **kwargs):
                        raise AssertionError("zero-episode reference must not call actor")

                asyncio.run(reference._run_agent_loop("Identical initial Task", UnusedFakeChat()))
                episode = PMAEpisode(agents["ga"], run_id="r", task_id="t",
                                     archive=root / "private")
                asyncio.run(episode.handle({"kind": "task_start", "sequence": 1,
                                            "event_id": "start", "run_id": "r",
                                            "task_id": "t",
                                            "initial_user_content": "Identical initial Task"}))
                self.assertEqual(captured["reference"], captured["ga"])
                self.assertEqual(reference._memory.status, agents["ga"]._memory.status)
                self.assertEqual(reference._pending_injection, agents["ga"]._pending_injection)
                self.assertEqual(len(captured["ga"]), 2)

    def test_private_phase_audit_failure_is_not_upstream_silence(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            requests, responses = root / "shared" / "requests", root / "shared" / "responses"
            requests.mkdir(parents=True)
            responses.mkdir()
            agent = construct_upstream(root / "agent")
            async def fake_call(*, prompt, system, tools=None):
                return LLMResponse(content="<no_intervention/>", tool_calls=[])
            agent._memory_llm.call = fake_call
            episode = PMAEpisode(agent, run_id="r", task_id="t", archive=root / "private")
            worker_main.install_transport_audit(agent, episode.archive)
            (requests / "first.json").write_text(json.dumps({
                "schema": "pma-ga-events-v1", "kind": "task_start",
                "event_id": "first", "sequence": 1, "run_id": "r", "task_id": "t",
                "initial_user_content": "public"}), encoding="utf-8")
            dispatcher = EventDispatcher(episode, requests, responses)
            with patch.object(worker_main, "append_private_audit",
                              side_effect=worker_main.PMAAuditIntegrityError("denied")):
                with self.assertRaises(worker_main.PMAAuditIntegrityError):
                    asyncio.run(dispatcher.serve_once())
            self.assertFalse((responses / "first.json").exists())

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

    def test_actual_ga_client_event_matches_host_dispatcher(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            requests, responses = root / "shared" / "requests", root / "shared" / "responses"
            requests.mkdir(parents=True)
            responses.mkdir()
            agent = construct_upstream(root / "agent")

            async def fake_memory_call(*, prompt, system, tools=None):
                return LLMResponse(content="<no_intervention/>", tool_calls=[])

            agent._memory_llm.call = fake_memory_call
            episode = PMAEpisode(agent, run_id="r", task_id="t", archive=root / "private")
            dispatcher = EventDispatcher(episode, requests, responses)
            ga_client = UpstreamPMAClient(run_id="r", task_id="t", requests=requests,
                                          responses=responses, deadline=time.time() + 5)

            async def run():
                pending = asyncio.create_task(asyncio.to_thread(
                    ga_client.exchange, 'task_start', initial_user_content='GA input'))
                while not pending.done():
                    await dispatcher.serve_once()
                    await asyncio.sleep(.01)
                self.assertEqual((await pending)['status'], 'started')
                self.assertEqual(episode.last_sequence, 1)

            asyncio.run(run())

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

    def test_independent_upstream_and_ga_event_prompts_match(self):
        """Run original actor loop separately from the GA event scheduling."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            public = "PUBLIC_ANALYSIS: both files affect the transaction"
            commands = ["tool alpha --read", "tool beta --read"]
            observation = json.dumps({"content": "RESULT_ALPHA and RESULT_BETA",
                                      "tool_results": ["RESULT_ALPHA", "RESULT_BETA"]},
                                     ensure_ascii=False)
            requests = {}
            agents = {}
            for arm in ("original", "ga"):
                agent = construct_upstream(root / arm)
                agents[arm] = agent
                requests[arm] = []

                async def memory_call(*, prompt, system, tools=None, arm=arm):
                    requests[arm].append((prompt, system,
                        json.dumps(tools, sort_keys=True, default=str) if tools is not None else None))
                    if tools:
                        return LLMResponse(content="", tool_calls=[])
                    return LLMResponse(content="<context_for_action>Keep the public clue.</context_for_action>")

                agent._memory_llm.call = memory_call

            reference = agents["original"]
            reference._context = SimpleNamespace()
            reference._max_episodes = 2
            reference._enable_summarize = False
            reference._session = SimpleNamespace(is_session_alive=lambda: asyncio.sleep(0, result=True))
            reference._setup_episode_logging = lambda *a: None
            reference._record_asciinema_marker = lambda *a: None
            reference._record_step_full = lambda *a, **k: None
            reference._dump_trajectory = lambda: None

            class FakeChat:
                total_input_tokens = total_output_tokens = total_cache_tokens = total_cost = 0

                async def chat(self, prompt, **kwargs):
                    return LLMResponse(content=public)

            actor_attempts = 0

            async def reference_actor(chat, prompt, *args):
                nonlocal actor_attempts
                await chat.chat(prompt)
                actor_attempts += 1
                if actor_attempts == 2:
                    return ([], False, "ERROR: bad actor envelope", None, None,
                            LLMResponse(content="bad actor envelope"))
                return (commands, False, "", public, None, LLMResponse(content=public))

            reference._handle_llm_interaction = reference_actor
            reference._execute_commands = lambda cmds, session: asyncio.sleep(
                0, result=(False, observation))
            asyncio.run(reference._run_agent_loop("Same public GA task", FakeChat()))

            ga = agents["ga"]
            episode = PMAEpisode(ga, run_id="r", task_id="t", archive=root / "private")

            async def ga_events():
                def event(kind, sequence, **fields):
                    return {"kind": kind, "event_id": f"e{sequence}", "sequence": sequence,
                            "run_id": "r", "task_id": "t", **fields}

                await episode.handle(event("task_start", 1,
                                           initial_user_content="Same public GA task"))
                first = await episode.handle(event("before_actor_call", 2, actor_attempt=1))
                self.assertIn("Keep the public clue.", first["reminder"])
                await episode.handle(event("actor_step", 3, actor_attempt=1,
                                           step_status="normal", response=public,
                                           commands=commands, observation=observation))
                await episode.handle(event("before_actor_call", 4, actor_attempt=2))
                await episode.handle(event("actor_step", 5, actor_attempt=2,
                                           step_status="parse_error",
                                           response="bad actor envelope"))

            asyncio.run(ga_events())
            self.assertEqual(requests["original"], requests["ga"])
            self.assertEqual(reference._accumulated_observations,
                             ga._accumulated_observations)
            self.assertEqual(reference._pending_injection, ga._pending_injection)
            self.assertEqual(len(requests["ga"]), 4)
            self.assertIsNotNone(requests["ga"][0][2])
            self.assertEqual(actor_attempts, 2)
            self.assertIn(public, requests["ga"][2][0])
            self.assertIn("RESULT_BETA", requests["ga"][3][0])


if __name__ == "__main__":
    unittest.main()
