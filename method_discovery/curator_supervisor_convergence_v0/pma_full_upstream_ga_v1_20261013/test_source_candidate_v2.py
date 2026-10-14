"""Zero-provider checks of the real upstream two-phase process with S2/R2 adapters."""
import asyncio
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor" / "pma_89e5c0d"
sys.path.insert(0, str(VENDOR / "src"))
sys.path.insert(0, str(VENDOR / "external" / "harbor" / "src"))
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from harbor.llms.base import LLMResponse
import litellm
from episode import PMAEpisode, construct_upstream
from source_memory_v2 import SourceMemoryV2
from static_source_screen import MANIFEST_V2, projected_events


def call(name, **kwargs):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=kwargs))


class Script:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    async def __call__(self, *, prompt, system, tools=None):
        self.requests.append({"prompt": prompt, "system": system, "tools": tools})
        if not self.replies:
            raise AssertionError("unexpected provider send")
        return self.replies.pop(0)


class V2Tests(unittest.TestCase):
    def make(self, variant, replies):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        agent = construct_upstream(Path(tmp.name) / "upstream", research_candidate=variant)
        fake = Script(replies)
        agent._memory_llm.call = fake
        return agent, fake, Path(tmp.name)

    def test_real_process_schema_transaction_receipts_and_next_phase(self):
        refs = [{"source_handle": "placeholder", "start_line": 1, "end_line": 1}]
        agent, fake, _ = self.make("S2", [])
        bank = agent.memory
        handle = bank.register_leaf("e1", "task_instruction", "Keep WAL.\nNo deletion.", 1,
                                    "initial_user_content", "a" * 64)
        refs[0]["source_handle"] = handle
        fake.replies.extend([
            LLMResponse(content="", tool_calls=[call("memory_save_knowledge", content="Keep WAL",
                statement_type="task_requirement", source_refs=refs)]),
            LLMResponse(content="<no_intervention/>"),
            LLMResponse(content="", tool_calls=[call("memory_delete", memory_id="absent")]),
            LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("Keep WAL.", 1))
        self.assertEqual(len(bank.knowledge), 1)
        transaction = agent._memory_agent.last_transaction
        self.assertEqual(transaction["before_bank"]["knowledge"], [])
        self.assertEqual(len(transaction["after_bank"]["knowledge"]), 1)
        schema = fake.requests[0]["tools"][0]["function"]["parameters"]
        self.assertIn("source_refs", schema["required"])
        self.assertTrue(schema["additionalProperties"] is False)
        self.assertIn("committed", fake.requests[1]["prompt"])
        asyncio.run(agent._memory_agent.process("Keep WAL.", 2))
        self.assertIn("Previous phase-1 execution receipts", fake.requests[2]["prompt"])
        self.assertIn("committed", fake.requests[2]["prompt"])
        self.assertIn("rejected", fake.requests[3]["prompt"])

    def test_atomic_save_delete_both_orders_and_collision(self):
        for first in ("memory_delete", "memory_save_knowledge"):
            with self.subTest(first=first):
                agent, fake, _ = self.make("S2", [])
                bank = agent.memory
                handle = bank.register_leaf("e1", "task_instruction", "Keep WAL.", 1,
                                            "initial_user_content", "b" * 64)
                ref = [{"source_handle": handle, "start_line": 1, "end_line": 1}]
                old = bank.save_sourced("knowledge", "old", "task_requirement", ref)
                prior = bank.to_dict()
                good = call("memory_delete", memory_id=old)
                bad = call("memory_save_knowledge", content="bad", statement_type="task_requirement",
                           source_refs=[{"source_handle": "missing", "start_line": 1, "end_line": 1}])
                calls = [good, bad] if first == "memory_delete" else [bad, good]
                fake.replies.extend([LLMResponse(content="", tool_calls=calls),
                                     LLMResponse(content="<no_intervention/>")])
                asyncio.run(agent._memory_agent.process("Keep WAL.", 1))
                self.assertEqual(bank.to_dict(), prior)
                self.assertEqual(agent._memory_agent.last_transaction["before_bank"],
                                 agent._memory_agent.last_transaction["after_bank"])
                statuses = [r["status"] for r in agent._memory_agent.last_receipts]
                self.assertIn("rejected", statuses)
                self.assertIn("transaction_aborted", statuses)
                self.assertEqual(agent._memory_agent.collateral_aborts, 1)

    def test_valid_save_with_invalid_delete_rolls_back_in_both_orders(self):
        for bad_first in (True, False):
            with self.subTest(bad_first=bad_first):
                agent, fake, _ = self.make("S2", [])
                bank = agent.memory
                handle = bank.register_leaf("e1", "task_instruction", "Keep WAL", 1,
                                            "initial_user_content", "b" * 64)
                ref = [{"source_handle": handle, "start_line": 1, "end_line": 1}]
                prior = bank.to_dict()
                good = call("memory_save_knowledge", content="Keep WAL",
                            statement_type="task_requirement", source_refs=ref)
                bad = call("memory_delete", memory_id="missing")
                calls = [bad, good] if bad_first else [good, bad]
                fake.replies.extend([LLMResponse(content="", tool_calls=calls),
                                     LLMResponse(content="<no_intervention/>")])
                asyncio.run(agent._memory_agent.process("Keep WAL", 1))
                self.assertEqual(bank.to_dict(), prior)
                self.assertEqual({r["status"] for r in agent._memory_agent.last_receipts},
                                 {"rejected", "transaction_aborted"})
                self.assertEqual(bank.search_knowledge("WAL"), [])

    def test_status_update_is_included_in_abort_and_empty_phase_is_no_change(self):
        agent, fake, _ = self.make("S2", [])
        bank = agent.memory
        fake.replies.extend([LLMResponse(content="", tool_calls=[
            call("memory_update_status", content="working"),
            call("memory_delete", memory_id="missing")]),
            LLMResponse(content="<no_intervention/>"),
            LLMResponse(content="", tool_calls=[]), LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("task", 1))
        self.assertEqual(bank.status, "")
        self.assertEqual(agent._memory_agent.last_receipts[0]["status"], "transaction_aborted")
        asyncio.run(agent._memory_agent.process("task", 2))
        self.assertEqual(agent._memory_agent.last_receipts, [])
        self.assertTrue(agent._memory_agent.last_transaction["committed"])

    def test_text_tool_fallback_is_rejected_whole_in_both_orders(self):
        good = "<tool_call><function=memory_update_status><parameter=content>B</parameter></function></tool_call>"
        bad = "<tool_call><function=memory_delete><parameter=memory_id>missing</parameter>"
        for variant in ("S2", "R2"):
            for text in (good + bad, bad + good, bad, good):
                with self.subTest(variant=variant, text=text):
                    agent, fake, _ = self.make(variant, [
                        LLMResponse(content=text, tool_calls=[]),
                        LLMResponse(content="<no_intervention/>")])
                    bank = agent.memory
                    bank.update_status("A")
                    before = bank.to_dict()
                    result = asyncio.run(agent._memory_agent.process("task", 1))
                    self.assertEqual(bank.to_dict(), before)
                    self.assertEqual(len(fake.requests), 2)
                    self.assertFalse(result.operations[0].success)
                    self.assertEqual(agent._memory_agent.last_transaction["status"],
                                     "format_rejected")
                    self.assertEqual(agent._memory_agent.last_receipts[0]["error_code"],
                                     "text_tool_call_forbidden")
        agent, _, _ = self.make("S2", [
            LLMResponse(content="ordinary prose", tool_calls=[]),
            LLMResponse(content="<no_intervention/>")])
        result = asyncio.run(agent._memory_agent.process("task", 1))
        self.assertEqual(result.operations, [])
        self.assertEqual(agent._memory_agent.last_transaction["status"], "no_change")

    def test_rollback_relabels_stage_local_no_change_and_feedback(self):
        agent, fake, _ = self.make("S2", [
            LLMResponse(content="", tool_calls=[
                call("memory_update_status", content="B"),
                call("memory_update_status", content="B"),
                call("memory_delete", memory_id="absent")]),
            LLMResponse(content="<no_intervention/>"),
            LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>")])
        agent.memory.update_status("A")
        result = asyncio.run(agent._memory_agent.process("task", 1))
        self.assertEqual(agent.memory.status, "A")
        self.assertEqual([r["status"] for r in agent._memory_agent.last_receipts],
                         ["transaction_aborted", "transaction_aborted", "rejected"])
        self.assertEqual([op.success for op in result.operations], [False, False, False])
        self.assertEqual(agent._memory_agent.collateral_aborts, 2)
        self.assertIn('"status": "transaction_aborted"', fake.requests[1]["prompt"])
        self.assertIn('"status": "rejected"', fake.requests[1]["prompt"])
        asyncio.run(agent._memory_agent.process("task", 2))
        self.assertIn('"status": "transaction_aborted"', fake.requests[2]["prompt"])
        self.assertEqual(agent._memory_agent.last_transaction["status"], "no_change")

    def test_phase1_transport_failure_does_not_reuse_prior_receipts(self):
        agent, fake, _ = self.make("S2", [
            LLMResponse(content="", tool_calls=[call("memory_update_status", content="B")]),
            LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("task", 1))
        self.assertEqual(agent._memory_agent.last_transaction["status"], "committed")
        with self.assertRaises(AssertionError):
            asyncio.run(agent._memory_agent.process("task", 2))
        self.assertEqual(len(fake.requests), 3)
        self.assertEqual(agent._memory_agent.last_receipts, [])
        self.assertEqual(agent._memory_agent.last_transaction["status"],
                         "phase1_request_failed")
        self.assertIn('"status": "committed"', fake.requests[2]["prompt"])

    def test_successful_delete_and_procedural_index_invalidation(self):
        agent, fake, _ = self.make("S2", [])
        bank = agent.memory
        handle = bank.register_leaf("e1", "tool_observation", "compile failed", 1,
                                    "observation/tool_results/0/content", "b" * 64)
        ref = [{"source_handle": handle, "start_line": 1, "end_line": 1}]
        memory_id = bank.save_sourced("procedural", "compile failed", "tool_observation", ref)
        self.assertEqual(bank.search_procedural("compile")[0].id, memory_id)
        fake.replies.extend([LLMResponse(content="", tool_calls=[
            call("memory_delete", memory_id=memory_id)]),
            LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("compile failed", 2))
        self.assertEqual(bank.search_procedural("compile"), [])
        self.assertTrue(any(row["action"] == "upstream_delete" for row in bank.history))
        self.assertEqual(agent._memory_agent.last_receipts[0]["status"], "committed")

    def test_roles_visibility_and_line_ranges(self):
        bank = SourceMemoryV2()
        instruction = bank.register_leaf("e1", "task_instruction", "A\nB\n", 1,
                                         "initial_user_content", "c" * 64)
        report = bank.register_leaf("e2", "agent_report", "I saw success", 2,
                                    "response", "d" * 64)
        tool = bank.register_leaf("e2", "tool_observation", "failed", 2,
                                  "observation/tool_results/0/content", "d" * 64)
        self.assertEqual(bank.excerpt(bank.resolve_refs([{
            "source_handle": instruction, "start_line": 1, "end_line": 2}],
            "task_requirement")[0]), "A\nB")
        with self.assertRaises(ValueError):
            bank.resolve_refs([{"source_handle": report, "start_line": 1, "end_line": 1}],
                              "tool_observation")
        with self.assertRaises(ValueError):
            bank.resolve_refs([{"source_handle": tool, "start_line": 2, "end_line": 3}], "inference")
        bank.current_source_ids = ["e1:initial_user_content"]
        with self.assertRaises(ValueError):
            bank.resolve_refs([{"source_handle": tool, "start_line": 1, "end_line": 1}], "inference")

    def test_unicode_crlf_blank_and_last_line_boundaries(self):
        bank = SourceMemoryV2()
        handle = bank.register_leaf("e1", "task_instruction", "甲\r\n\r\n乙\u2028末行", 1,
                                    "initial_user_content", "c" * 64)
        self.assertEqual(bank.visible_lines()[0]["numbered_lines"],
                         ["1: 甲", "2: ", "3: 乙", "4: 末行"])
        selected = bank.resolve_refs([{"source_handle": handle, "start_line": 3,
                                       "end_line": 4}], "task_requirement")[0]
        self.assertEqual(bank.excerpt(selected), "乙\u2028末行")
        blank = {"source_handle": handle, "start_line": 2, "end_line": 2}
        with self.assertRaises(ValueError):
            bank.resolve_refs([blank], "task_requirement")
        tampered = {**selected, "start_line": 2}
        self.assertFalse(bank.source_ref_valid(tampered))

    def test_old_bound_excerpt_can_be_explicitly_inherited_not_newly_cited(self):
        bank = SourceMemoryV2()
        old_handle = bank.register_leaf("e1", "task_instruction", "Keep WAL", 1,
                                        "initial_user_content", "1" * 64)
        old_ref = [{"source_handle": old_handle, "start_line": 1, "end_line": 1}]
        memory_id = bank.save_sourced("knowledge", "Keep WAL", "task_requirement", old_ref)
        bank.register_leaf("e2", "agent_report", "I checked", 2, "response", "2" * 64)
        bank.current_source_ids = ["e2:response"]
        with self.assertRaises(ValueError):
            bank.resolve_refs(old_ref, "task_requirement")
        evidence_handle = bank.sources["e2:response"]["handle"]
        evidence = bank.resolve_refs([{"source_handle": evidence_handle, "start_line": 1,
                                       "end_line": 1}], "agent_report")
        new_id = bank.revise(memory_id, "Keep WAL, based on original instruction",
                             "task_requirement", [], "retain original source", evidence, [0])
        self.assertEqual(bank.excerpt(bank.metadata[new_id]["source_refs"][0]), "Keep WAL")
        with self.assertRaises(ValueError):
            bank.revise(new_id, "bad", "task_requirement", [], "bad inheritance", evidence, [3])

    def test_actual_episode_splits_working_memory_from_tool_result(self):
        agent, fake, root = self.make("S2", [LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>"), LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>")])
        episode = PMAEpisode(agent, run_id="r", task_id="t", archive=root / "episode")
        base = {"run_id": "r", "task_id": "t"}
        asyncio.run(episode.handle({**base, "kind": "task_start", "event_id": "e1",
            "sequence": 1, "initial_user_content": "Task text", "source_record_sha256": "e" * 64}))
        asyncio.run(episode.handle({**base, "kind": "before_actor_call", "event_id": "e2",
            "sequence": 2, "actor_attempt": 1}))
        observation = json.dumps({"content": "working memory says pass", "tool_results": [
            {"tool_use_id": "x", "content": "real tool failed"}]})
        asyncio.run(episode.handle({**base, "kind": "actor_step", "event_id": "e3",
            "sequence": 3, "actor_attempt": 1, "step_status": "normal", "response": "checking",
            "commands": [], "observation": observation, "source_record_sha256": "f" * 64}))
        visible = agent.memory.visible_lines()
        self.assertEqual(next(row["role"] for row in visible if "working memory" in str(row)),
                         "agent_report")
        self.assertEqual(next(row["role"] for row in visible if "real tool failed" in str(row)),
                         "tool_observation")
        self.assertIn("real tool failed", fake.requests[2]["prompt"])

    def test_r2_revision_reload_and_pending_reference_invalidation(self):
        agent, fake, root = self.make("R2", [])
        bank = agent.memory
        old_handle = bank.register_leaf("e1", "task_instruction", "Keep WAL", 1,
                                        "initial_user_content", "1" * 64)
        old_ref = [{"source_handle": old_handle, "start_line": 1, "end_line": 1}]
        old_id = bank.save_sourced("knowledge", "Keep WAL", "task_requirement", old_ref)
        agent._memory_agent.last_delivery_status = "selected_validated_not_delivered"
        agent._memory_agent.last_reminder_refs = [{"id": old_id, "version": 1}]
        agent._memory_agent.last_reminder_identities = [agent._memory_agent._memory_identity(old_id)]
        new_handle = bank.register_leaf("e2", "tool_observation", "WAL has been removed", 2,
                                        "observation/tool_results/0/content", "2" * 64)
        new_ref = [{"source_handle": new_handle, "start_line": 1, "end_line": 1}]
        fake.replies.extend([LLMResponse(content="", tool_calls=[call("memory_reconcile",
            memory_id=old_id, decision="revise", reason="new tool observation",
            evidence_refs=new_ref, content="WAL absent", statement_type="tool_observation",
            source_refs=new_ref)]), LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("WAL has been removed", 2))
        self.assertFalse(agent._memory_agent.pending_refs_valid())
        self.assertIsNone(bank.get(old_id))
        new_id = bank.knowledge[0].id
        self.assertEqual(bank.search_knowledge("absent")[0].id, new_id)
        path = root / "bank.json"
        bank.save_to_file(path)
        loaded = SourceMemoryV2.load_from_file(path)
        self.assertEqual(loaded.knowledge[0].id, new_id)
        self.assertEqual(loaded.search_knowledge("absent")[0].id, new_id)
        self.assertTrue(any(h["action"] == "revise" for h in loaded.history))

    def test_bad_json_unknown_tool_and_missing_source_abort_without_mutation(self):
        agent, fake, _ = self.make("S2", [])
        bank = agent.memory
        handle = bank.register_leaf("e1", "task_instruction", "Keep WAL", 1,
                                    "initial_user_content", "3" * 64)
        ref = [{"source_handle": handle, "start_line": 1, "end_line": 1}]
        prior = bank.to_dict()
        fake.replies.extend([LLMResponse(content="", tool_calls=[
            call("memory_save_knowledge", content="Keep WAL", statement_type="task_requirement",
                 source_refs=ref),
            SimpleNamespace(function=SimpleNamespace(name="memory_delete", arguments="{bad-json")),
            call("memory_unknown", content="x")]), LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("Keep WAL", 1))
        self.assertEqual(bank.to_dict(), prior)
        self.assertEqual([r["status"] for r in agent._memory_agent.last_receipts],
                         ["transaction_aborted", "rejected", "rejected"])
        self.assertEqual(agent._memory_agent.last_receipts[2]["error_code"], "unknown_tool")

    def test_schema_and_local_validation_both_reject_nested_extra_and_coercion(self):
        agent, fake, _ = self.make("S2", [])
        bank = agent.memory
        handle = bank.register_leaf("e1", "task_instruction", "Keep WAL", 1,
                                    "initial_user_content", "3" * 64)
        bad_refs = [
            [{"source_handle": handle, "start_line": "1", "end_line": 1}],
            [{"source_handle": handle, "start_line": 1, "end_line": 1, "extra": True}],
        ]
        fake.replies.extend([LLMResponse(content="", tool_calls=[
            call("memory_save_knowledge", content="Keep WAL", statement_type="task_requirement",
                 source_refs=refs) for refs in bad_refs]),
            LLMResponse(content="<no_intervention/>")])
        asyncio.run(agent._memory_agent.process("Keep WAL", 1))
        self.assertEqual(bank.knowledge, [])
        self.assertEqual([r["error_code"] for r in agent._memory_agent.last_receipts],
                         ["argument_shape", "argument_shape"])
        nested = fake.requests[0]["tools"][0]["function"]["parameters"]["properties"][
            "source_refs"]["items"]
        self.assertFalse(nested["additionalProperties"])
        self.assertEqual(nested["required"], ["source_handle", "start_line", "end_line"])

    def test_host_integrity_exception_blocks_phase2_and_is_not_model_rejection(self):
        agent, fake, root = self.make("S2", [])
        fake.replies.append(LLMResponse(content="", tool_calls=[call(
            "memory_save_knowledge", content="Keep WAL", statement_type="task_requirement",
            source_refs=[{"source_handle": "irrelevant", "start_line": 1, "end_line": 1}])]))
        episode = PMAEpisode(agent, run_id="r", task_id="t", archive=root / "episode")
        event = {"kind": "task_start", "run_id": "r", "task_id": "t", "event_id": "e1",
                 "sequence": 1, "source_record_sha256": "9" * 64,
                 "initial_user_content": "Keep WAL"}
        handle = "s" + __import__("hashlib").sha256("e1:initial_user_content".encode()).hexdigest()[:12]
        fake.replies[0].tool_calls[0].function.arguments["source_refs"][0]["source_handle"] = handle
        with patch.object(SourceMemoryV2, "save_sourced", side_effect=OSError("disk-like host fault")):
            asyncio.run(episode.handle(event))
        self.assertEqual(len(fake.requests), 1)
        self.assertIsInstance(agent._memory_agent._fatal_error, OSError)
        self.assertEqual(agent.memory.knowledge, [])
        self.assertEqual(agent._memory_agent.last_receipts[0]["status"], "integrity_error")

    def test_real_litellm_serialization_boundary_with_local_only_response(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        profile = {"provider": "anthropic", "api_mode": "messages", "model": "claude-opus-4-8",
            "thinking_type": "adaptive", "reasoning_effort": "high", "temperature": 1,
            "max_tokens": 8192, "read_timeout": 300, "apibase": "https://offline.invalid",
            "apikey": "SENTINEL_DO_NOT_SEND"}
        agent = construct_upstream(Path(tmp.name) / "upstream", memory_profile=profile,
                                   research_candidate="S2")
        sent = []

        async def only_fake(**kwargs):
            sent.append(kwargs)
            if len(sent) > 2:
                raise AssertionError("unexpected model request")
            if len(sent) == 1:
                content_blocks = kwargs["messages"][-1]["content"]
                user_text = (content_blocks if isinstance(content_blocks, str) else
                             "".join(block["text"] for block in content_blocks if block.get("type") == "text"))
                source = next(row for row in json.loads(user_text.split(
                    "## Numbered visible public source leaves\n", 1)[1].split(
                    "\n## Previous phase-1 execution receipts", 1)[0])
                    if row["role"] == "task_instruction")
                args = json.dumps({"content": "Keep WAL", "statement_type": "task_requirement",
                    "source_refs": [{"source_handle": source["source_handle"],
                                     "start_line": 1, "end_line": 1}]})
                tool_calls = [{"id": "local-1", "type": "function", "function": {
                    "name": "memory_save_knowledge", "arguments": args}}]
                content = ""
            else:
                tool_calls = None
                content = "<no_intervention/>"
            return litellm.ModelResponse(model="claude-opus-4-8", choices=[{
                "message": {"content": content, "tool_calls": tool_calls},
                "finish_reason": "stop"}], usage={"prompt_tokens": 2, "completion_tokens": 1})

        episode = PMAEpisode(agent, run_id="r", task_id="t", archive=Path(tmp.name) / "archive")
        event = {"kind": "task_start", "run_id": "r", "task_id": "t", "event_id": "e1",
                 "sequence": 1, "source_record_sha256": "9" * 64,
                 "initial_user_content": "Keep WAL and diagnose recovery."}
        with patch("litellm.acompletion", only_fake):
            asyncio.run(episode.handle(event))
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0]["model"], "anthropic/claude-opus-4-8")
        self.assertEqual(sent[0]["max_tokens"], 8192)
        self.assertEqual(sent[0]["thinking"], {"type": "adaptive"})
        self.assertEqual(sent[0]["reasoning_effort"], "high")
        self.assertIn("start_line", json.dumps(sent[0]["tools"]))
        self.assertNotIn("tools", sent[1])
        self.assertIn("committed", json.dumps(sent[1]["messages"][-1]["content"]))
        self.assertEqual(len(agent.memory.knowledge), 1)

    def test_archived_escaped_stdout_is_explicitly_decoded_and_bounded(self):
        case = json.loads(MANIFEST_V2.read_text(encoding="utf-8"))["cases"][0]
        events = projected_events(case, "r")[:3]
        agent, fake, root = self.make("S2", [LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>"), LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="<no_intervention/>")])
        episode = PMAEpisode(agent, run_id="r", task_id=case["task"], archive=root / "episode")
        for event in events:
            asyncio.run(episode.handle(event))
        decoded = next(row for row in agent.memory.sources.values()
                       if row.get("field_path") == "observation/tool_results/0/content/stdout")
        self.assertIn("drwx", decoded["text"])
        self.assertIn("\n", decoded["text"])
        self.assertEqual(decoded["raw_sha256"], events[2]["source_record_sha256"])
        selection = {"source_handle": decoded["handle"], "start_line": 1, "end_line": 1}
        ref = agent.memory.resolve_refs([selection], "tool_observation")[0]
        self.assertTrue(agent.memory.source_ref_valid(ref))
        with self.assertRaises(ValueError):
            agent.memory.resolve_refs([{**selection, "source_handle": "wrong"}], "tool_observation")
