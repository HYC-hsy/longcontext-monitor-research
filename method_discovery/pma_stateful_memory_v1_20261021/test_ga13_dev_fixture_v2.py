"""Read archived GA13 bytes as an offline development observation; never run its command."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from .engine import CycleEngine
from .budget import TokenProxy
from .source import digest
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf
from .test_engine import ScriptedProvider


ARCHIVE = (Path(__file__).resolve().parents[1] /
    "pos_pma_shared_view_v1_20261020/raw_live_sqlite_contract_v2/pos/"
    "events.host.jsonl.part001.jsonl")
CALL = "toolu_exwuJ8l8ii6K0TOkaI8jn6"


class GA13DevelopmentFixture(unittest.TestCase):
    def test_archived_observation_is_separate_from_new_fake_decision(self):
        raw = ARCHIVE.read_bytes()
        action = result = None
        action_line = result_line = None
        for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
            if CALL not in line:
                continue
            row = json.loads(line)
            payload = row.get("payload", {})
            if row.get("kind") == "tool_started" and payload.get("id") == CALL:
                action, action_line = payload, number
            elif row.get("kind") == "tool_outcome" and payload.get(
                    "tool_use_id") == CALL:
                result, result_line = payload, number
        self.assertEqual((action_line, result_line), (52, 53))
        self.assertEqual(result["result"]["exit_code"], 127)
        stdout = result["result"]["stdout"]
        self.assertIn("sqlite3: command not found", stdout)
        self.assertIn("PATH", stdout)
        action_text = json.dumps(action["arguments"], ensure_ascii=False,
                                 sort_keys=True, separators=(",", ":"))
        sources = []
        for source_id, kind, path, text in (
                ("ga13-action", "executed_action", "payload.arguments", action_text),
                ("ga13-stdout", "tool_result", "payload.result.stdout", stdout)):
            source = leaf(text, source_id=source_id, source_kind=kind)
            source.update(event_id=CALL, event_seq=1, ga_turn=13,
                          field_path=path)
            sources.append(source)
        with tempfile.TemporaryDirectory() as root:
            store = MemoryStore(Path(root) / "ga13-dev.sqlite3")
            try:
                store.initialize(empty_snapshot(), leaf("task"))
                store.append_event({"event_id": "ga13-host-batch-dev", "event_seq": 1,
                    "kind": "action_batch", "occurred_at_step": 13,
                    "source_ids": [item["source_id"] for item in sources],
                    "payload": {"actions": [{"tool_use_id": CALL}],
                        "exit_code": 127, "fixture_origin": "archived_observation_only"}},
                    sources)
                provider = ScriptedProvider()
                result_cycle = CycleEngine(store, provider,
                    task_text="task").run("ga13-dev")
                self.assertEqual(result_cycle["status"], "committed_selection_silent")
                self.assertEqual(result_cycle["logical_calls"], 3)
                sent = json.loads(provider.calls[0]["messages"][1]["content"])
                leaves = sent["observation_batch"]["events"][0]["source_leaves"]
                self.assertEqual(next(item for item in leaves if item["source_id"] ==
                    "ga13-stdout")["text"], stdout)
                self.assertEqual(next(item for item in leaves if item["source_id"] ==
                    "ga13-action")["text"], action_text)
                self.assertNotIn("reward", provider.calls[0]["messages"][1]["content"])
                self.assertEqual(result_cycle["commit"]["event_seq"], 1)
                self.assertEqual(len(provider.calls), 3)
                self.assertEqual(len(raw), ARCHIVE.stat().st_size)
                self.assertEqual(len(hashlib.sha256(raw).hexdigest()), 64)
                proxy = TokenProxy()
                print(json.dumps({"fixture": "ga13_development_v2",
                    "archive_sha256": hashlib.sha256(raw).hexdigest(),
                    "archive_bytes": len(raw), "action_line": action_line,
                    "result_line": result_line, "call_id": CALL,
                    "source_identity": "archived_observation_only",
                    "candidate_identity": "developer_fake",
                    "calls": [{"role": call["role"],
                        "messages_sha256": digest(call["messages"]),
                        "request_size": {key: proxy.measure(call["messages"])[key]
                            for key in ("characters", "utf8_bytes", "proxy_tokens")}}
                        for call in provider.calls]}, sort_keys=True))
            finally:
                store.close()
