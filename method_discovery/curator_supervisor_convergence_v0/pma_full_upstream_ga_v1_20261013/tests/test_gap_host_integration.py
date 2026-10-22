"""Direct gap view through the real upstream episode and its message boundary."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from harbor.llms.base import LLMResponse
from episode import PMAEpisode, construct_upstream
from gap_memory_agent import GapMemoryAgent
from gap_store import GapMemory


def event(kind, number, **fields):
    return dict(kind=kind, sequence=number, event_id=f"event-{number}",
                run_id="gap-test", task_id="synthetic", **fields)


class GapHostTests(unittest.TestCase):
    def test_task_binding_same_bank_and_two_phase_cycle(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            agent = construct_upstream(root / "upstream", research_candidate="pma_gap_memory_v0")
            self.assertIsInstance(agent._memory, GapMemory)
            self.assertIsInstance(agent._memory_agent, GapMemoryAgent)
            self.assertIs(agent._memory, agent._memory_agent.memory)
            self.assertIs(agent._memory, agent._memory_agent.gaps)
            seen = []

            async def scripted(*, prompt, system, tools=None):
                seen.append((agent._memory_agent.transport_phase, prompt, tools))
                phase = agent._memory_agent.transport_phase
                if phase == "maintenance":
                    call = SimpleNamespace(function=SimpleNamespace(
                        name="memory_save_gap", arguments=json.dumps({
                            "content": "Verify the synthetic result."})))
                    return LLMResponse(content="", tool_calls=[call])
                if phase == "selection":
                    return LLMResponse(content="<context_for_action>Check result.</context_for_action>")
                raise AssertionError(phase)

            agent._memory_llm.call = scripted
            episode = PMAEpisode(agent, run_id="gap-test", task_id="synthetic",
                                 archive=root / "archive")

            async def run():
                started = await episode.handle(event("task_start", 1,
                    initial_user_content="Original synthetic task text"))
                self.assertTrue(started["triggered"])
                reminder = await episode.handle(event("before_actor_call", 2,
                    actor_attempt=1))
                self.assertIn("Check result.", reminder["reminder"])
                return await episode.handle(event("task_end", 3, terminal={"result": "done"}))

            self.assertEqual(asyncio.run(run())["status"], "saved")
            self.assertEqual(agent._memory_agent.task, "Original synthetic task text")
            self.assertEqual([row[0] for row in seen],
                             ["maintenance", "selection"])
            self.assertIn("Original synthetic task text", seen[0][1])
            self.assertIn("Verify the synthetic result.", seen[1][1])
            cycle = json.loads((root / "archive/gap_cycle.jsonl").read_text().splitlines()[0])
            self.assertEqual(cycle["report"]["mode"], "direct_two_phase")
            self.assertEqual(cycle["report"]["actual_phase2_prompt"], seen[1][1])
            self.assertEqual(len(cycle["formal_gaps"]), 1)
            saved = json.loads((root / "archive/memory.json").read_text())
            self.assertEqual(len(saved["gaps"]), 1)

    def test_gap_tool_failure_is_recorded_without_review_or_rollback(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            agent = construct_upstream(root / "upstream", research_candidate="pma_gap_memory_v0")

            seen = []

            async def scripted(*, prompt, system, tools=None):
                phase = agent._memory_agent.transport_phase
                seen.append(phase)
                if phase == "maintenance":
                    calls = [SimpleNamespace(function=SimpleNamespace(name=name,
                             arguments=json.dumps(args))) for name, args in [
                                 ("memory_save_gap", {"content": "Saved gap"}),
                                 ("memory_delete", {"memory_id": "gap_missing"})]]
                    return LLMResponse(content="", tool_calls=calls)
                return LLMResponse(content="<no_intervention/>")

            agent._memory_llm.call = scripted
            episode = PMAEpisode(agent, run_id="gap-test", task_id="synthetic",
                                 archive=root / "archive")
            asyncio.run(episode.handle(event("task_start", 1,
                initial_user_content="Original synthetic task text")))
            cycle = json.loads((root / "archive/gap_cycle.jsonl").read_text().splitlines()[0])
            self.assertEqual(seen, ["maintenance", "selection"])
            self.assertEqual(cycle["formal_gaps"][0]["content"], "Saved gap")
            self.assertEqual(cycle["report"]["errors"][0]["memory_id"], "gap_missing")
            self.assertIn("Saved gap", cycle["report"]["actual_phase2_prompt"])


if __name__ == "__main__":
    unittest.main()
