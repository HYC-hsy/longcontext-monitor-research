import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import replay


def fixture():
    return {"model": "example", "stream": True, "thinking": "[EXCLUDED_PRIVATE_FIELD]",
            "context_management": {}, "metadata": {},
            "tools": [{"name": "record_only"}], "system": [{"type": "text", "text": "system"}],
            "messages": [{"role": "user", "content": [{"type": "text", "text": "past evidence"}]},
                         {"role": "assistant", "content": [
                             replay.PRIVATE_BLOCK, {"type": "tool_use", "id": "x"}]},
                         {"role": "user", "content": [
                             {"type": "tool_result", "tool_use_id": "x", "content": '{"stdout":"3"}'},
                             {"type": "text", "text": "last", "cache_control": {"type": "ephemeral"}}]}]}


CASE = {"id": "case", "event": "evt_1", "evidence": [
    {"field": ["messages", 0, "content", 0, "text"], "label": "Earlier", "literal": "past evidence"},
    {"field": ["messages", 2, "content", 0, "content"], "label": "Current", "json_key": "stdout", "literal": "3"}]}


class ReplayTests(unittest.TestCase):
    def test_only_last_text_changes_and_models_never_see_labels(self):
        body = fixture()
        self.assertEqual(replay.intervention(body, CASE, "none"), body)
        for arm in ("generic", "paired"):
            result = replay.intervention(body, CASE, arm)
            last = result["messages"][-1]["content"][-1]
            original, suffix = last["text"].split("\n\n[Reminder]\n", 1)
            self.assertEqual(original, "last")
            self.assertTrue(suffix.startswith(replay.GENERIC))
            self.assertEqual("past evidence" in suffix, arm == "paired")
            self.assertNotIn("evt_1", suffix)
            self.assertNotIn(arm, suffix)
            last["text"] = original
            self.assertEqual(result, body)

    def test_provenance_failure(self):
        body = fixture()
        for wrong in ("future evidence", ""):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                replay.passage(body, {**CASE["evidence"][0], "literal": wrong})

    def test_projection_does_not_rewrite_nonprivate_content(self):
        body = fixture()
        normal = replay.public_normalized(body)
        self.assertFalse(replay.PLACEHOLDER.search(replay.dump(normal).decode()))
        normal["messages"][1]["content"].insert(0, replay.PRIVATE_BLOCK)
        for key in ("thinking", "context_management", "metadata"):
            normal[key] = body[key]
        self.assertEqual(normal, body)

    def test_raw_body_must_match_pinned_original_digest(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            source = root / "case.json"
            body = fixture()
            source.write_bytes(replay.dump(body))
            self.assertEqual(replay.full_body({"sha256": replay.sha(replay.dump(body))}, root, CASE), body)
            with self.assertRaisesRegex(ValueError, "digest"):
                replay.full_body({"sha256": "0" * 64}, root, CASE)

    def test_slot_order_rotates_and_covers_arms(self):
        order = [arm for _, _, arm in replay.schedule([CASE], 3)]
        self.assertEqual(order, ["none", "generic", "paired", "generic", "paired", "none",
                                 "paired", "none", "generic"])

    def test_hash_lock_rejects_unknown_archive_before_extraction(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "wrong.zip"
            path.write_bytes(b"not the archive")
            with self.assertRaisesRegex(ValueError, "checksum"):
                replay.archive_events(path, {"archive_sha256": "bad", "cases": []})

    def test_transport_uses_original_https_endpoint_no_redirects(self):
        with TemporaryDirectory() as d, patch.dict(os.environ, {"TASK_REPLAY_API_KEY": "unit-key"}):
            p = Path(d) / "transport.json"
            url = "https://example.test/v1/messages"
            p.write_bytes(replay.dump({"endpoint": url, "headers": {"anthropic-version": "2023-06-01"}}))
            endpoint, headers = replay.transport(p, {replay.sha(url.encode())})
            self.assertEqual(endpoint, url + "?beta=true")
            self.assertEqual(headers["x-api-key"], "unit-key")
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                replay.transport(p, {"wrong"})
            self.assertIsNone(replay.NoRedirect().redirect_request(None, None, 302, "", {}, "https://else.test"))

    def test_sse_visible_blocks_only_and_failure(self):
        s = [
            {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking"}},
            {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "next"}},
            {"type": "content_block_start", "index": 2, "content_block": {
                "type": "tool_use", "id": "x", "name": "file_read", "input": {}}},
            {"type": "content_block_delta", "index": 2, "delta": {
                "type": "input_json_delta", "partial_json": '{"path":"/app"}'}},
        ]
        wire = lambda rows: b"\n".join(b"data: " + replay.dump(row) for row in rows)
        self.assertEqual(replay.visible_sse(wire(s)), ("incomplete_stream", []))
        self.assertEqual(replay.visible_sse(wire([{"type": "error"}])), ("provider_error", []))
        status, blocks = replay.visible_sse(wire(s + [{"type": "message_stop"}]))
        self.assertEqual(status, "complete")
        self.assertEqual([b["type"] for b in blocks], ["text", "tool_use"])
        self.assertEqual(blocks[1]["input"], {"path": "/app"})

    def test_mocked_matrix_failure_is_kept_without_retry_or_overwrite(self):
        with TemporaryDirectory() as d, patch.object(replay, "archive_events") as archive, \
                patch.object(replay, "transport") as transport, patch.object(replay, "submit") as submit:
            casefile = Path(d) / "cases.json"
            casefile.write_bytes(replay.dump({"archive_sha256": "x", "cases": [CASE]}))
            transport_cfg = Path(d) / "local.json"
            transport_cfg.write_bytes(b"{}")
            archive.return_value = {"case": {"content": fixture(), "sha256": "x", "provider_url_sha256": "y"}}
            transport.return_value = ("https://example.test", {"x-api-key": "secret"})
            submit.side_effect = [({"status": "http_error", "http": 429}, b"rate limit"),
                                  ({"status": "complete", "visible_blocks": []}, b"ok"),
                                  ({"status": "complete", "visible_blocks": []}, b"ok")]
            args = argparse.Namespace(archive=None, raw_dir=None, public_normalized=True, execute=True,
                                      transport=transport_cfg, out=Path(d) / "out", repeats=1)
            with patch.object(replay, "CASES", casefile):
                self.assertEqual(replay.run(args), (3, "public_normalized"))
                self.assertEqual(submit.call_count, 3)
                self.assertEqual(json.loads((args.out / "001.result.json").read_bytes())["http"], 429)
                with self.assertRaises(FileExistsError):
                    replay.run(args)
                self.assertEqual(submit.call_count, 3)

    @unittest.skipUnless(os.environ.get("TASK_REPLAY_TEST_ARCHIVE"), "set TASK_REPLAY_TEST_ARCHIVE")
    def test_real_archive_all_cases_both_offline_modes(self):
        with TemporaryDirectory() as d, patch.object(replay, "submit") as submit:
            for mode in (False, True):
                args = argparse.Namespace(archive=Path(os.environ["TASK_REPLAY_TEST_ARCHIVE"]),
                                          raw_dir=None, public_normalized=mode, execute=False,
                                          transport=None, out=Path(d) / str(mode), repeats=2)
                n, _ = replay.run(args)
                self.assertEqual(n, 24)
                p = json.loads((args.out / "plan.json").read_bytes())
                for slot in p["slots"]:
                    data = (args.out / (slot["slot"] + ".request.json")).read_bytes()
                    self.assertEqual(replay.sha(data), slot["request_sha256"])
                    if slot["arm"] == "none":
                        self.assertEqual(slot["request_sha256"], slot["base_sha256"])
                    if mode:
                        self.assertFalse(replay.PLACEHOLDER.search(data.decode()))
            submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
