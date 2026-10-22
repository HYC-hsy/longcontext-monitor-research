"""The proxy target selects optional context; it is not a live request gate."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .budget import TokenProxy
from .engine import CycleEngine
from .retrieval import WorksetBuilder
from .source import ContractError
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf
from .test_engine import ScriptedProvider, event


class SoftProxyBudgetTests(unittest.TestCase):
    def test_large_real_role_messages_reach_provider_without_credit_spend(self):
        text = "observed result " + "zx84Qp-17 " * 50000
        with tempfile.TemporaryDirectory() as folder:
            store = MemoryStore(Path(folder) / "state.sqlite3")
            try:
                store.initialize(empty_snapshot(), leaf("task"))
                store.append_event(*event(1, text))
                provider = ScriptedProvider(outcomes=("issues",),
                    create_requirement=True, create_state=True)
                engine = CycleEngine(store, provider, task_text="task")
                result = engine.run("oversized-repair")
                self.assertEqual(result["status"], "committed_selection_silent")
                self.assertEqual([call["role"] for call in provider.calls],
                    ["maintenance", "audit", "candidate_repair", "audit", "selection"])
                repair = provider.calls[2]["messages"]
                self.assertGreater(engine.proxy.measure(repair)["proxy_tokens"], 32768)
                self.assertIn(text, repair[1]["content"])
                self.assertEqual(sum(row["phase"] == "repair_credit_used" for row
                    in store.journal_rows(result["cycle_id"])), 1)
                self.assertEqual(store.snapshot()["committed_event_seq"], 1)
                notice = json.loads(provider.calls[1]["messages"][1]["content"])[
                    "budget_notice"]
                self.assertEqual(notice["input_proxy_soft_target"], 32768)
                self.assertIsNone(notice["input_proxy_hard_limit"])
            finally:
                store.close()

    def test_required_earliest_batch_and_pending_survive_soft_overflow(self):
        snapshot = empty_snapshot()
        first, first_sources = event(1, "first result " + "x" * 1000)
        second, second_sources = event(2, "second result")
        ledger = {item["source_id"]: item for item in first_sources + second_sources}
        work = WorksetBuilder(soft_target=100).build(snapshot, [first, second],
            ledger, [], "cycle", 2, lambda payload: len(json.dumps(payload)))
        self.assertEqual([item["event_seq"] for item in
                          work.observation_batch["events"]], [1])
        self.assertEqual(work.observation_batch["pending_after_batch_count"], 1)
        self.assertEqual(work.observation_batch["processing_range"]["to_event_seq"], 1)
        self.assertIn("first result", work.observation_batch["events"][0][
            "source_leaves"][1]["text"])

    def test_unknown_proxy_keeps_required_batch_and_records_unknown(self):
        class BrokenEncoder:
            def encode(self, *_args, **_kwargs):
                raise RuntimeError("offline encoder unavailable")
        proxy = TokenProxy()
        proxy.encoding = BrokenEncoder()
        size = proxy.measure([{"role": "user", "content": "hello"}])
        self.assertIsNone(size["proxy_tokens"])
        self.assertEqual(size["proxy_unavailable_reason"],
                         "proxy_encoding_failed:RuntimeError")
        self.assertGreater(size["utf8_bytes"], 0)
        snapshot = empty_snapshot()
        first, sources = event(1)
        work = WorksetBuilder().build(snapshot, [first],
            {item["source_id"]: item for item in sources}, [],
            "unknown", 1, lambda _payload: None)
        self.assertEqual(len(work.observation_batch["events"]), 1)
        with self.assertRaisesRegex(ContractError, "input_budget_exceeded"):
            TokenProxy(input_limit=1).enforce([{"role": "user", "content": "hello"}])
        with tempfile.TemporaryDirectory() as folder:
            store = MemoryStore(Path(folder) / "state.sqlite3")
            try:
                store.initialize(empty_snapshot(), leaf("task"))
                store.append_event(*event(1))
                provider = ScriptedProvider()
                result = CycleEngine(store, provider, task_text="task",
                                     token_proxy=proxy).run("unknown-proxy")
                self.assertEqual(result["status"], "committed_selection_silent")
                prepared = [row["body"] for row in store.journal_rows(result["cycle_id"])
                            if row["phase"] == "call_prepared"]
                self.assertTrue(prepared)
                self.assertTrue(all(row["input_size"]["proxy_tokens"] is None
                                    for row in prepared))
                self.assertEqual(len(provider.calls), 3)
            finally:
                store.close()

    def test_missing_local_cache_never_fetches_in_soft_mode(self):
        import tiktoken.registry
        with tempfile.TemporaryDirectory() as folder, patch.dict(
                os.environ, {"TIKTOKEN_CACHE_DIR": folder}), patch.dict(
                tiktoken.registry.ENCODINGS, {}, clear=True):
            proxy = TokenProxy()
            self.assertIsNone(proxy.measure([])["proxy_tokens"])
            self.assertEqual(proxy.unavailable_reason, "FileNotFoundError")
            with self.assertRaisesRegex(ContractError, "tokenizer_unavailable"):
                TokenProxy(input_limit=1)

    def test_omission_manifest_is_not_another_hard_gate(self):
        snapshot = empty_snapshot()
        # The source bundle is mandatory for an open gap; no optional item may
        # displace it. A long omission list must itself remain model-visible.
        snapshot["B"]["W"]["entities"] = [{"entity_id": "e"}]
        from .test_retrieval import record
        states = [record(number) for number in range(12)]
        snapshot["B"]["W"]["states"] = states
        source = leaf("observed", source_id="source")
        source.update(event_id="batch", event_seq=1, ga_turn=1)
        # Optional records have no refs in this fixture, so they can be bundled.
        work = WorksetBuilder(soft_target=100).build(snapshot, [],
            {"source": source}, states, "omissions", 0,
            lambda payload: len(json.dumps(payload)))
        self.assertEqual(len(work.omissions), len(states))
        self.assertEqual(work.optional_bundles, [])


if __name__ == "__main__":
    unittest.main()
