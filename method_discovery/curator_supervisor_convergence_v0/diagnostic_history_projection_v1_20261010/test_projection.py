import copy
import unittest

from .projection import (PREFIX, canonical, digest, parse_rendered, project,
                         render, source_request)


class ProjectionTests(unittest.TestCase):
    def test_frozen_identity_counts_and_tail(self):
        h, r, m = project()
        self.assertEqual(len(h["messages"]), 96)
        self.assertEqual(len(r["messages"]), 9)
        self.assertEqual((m["retained_count"], m["removed_count"]), (182, 50))
        self.assertEqual((m["source_early_tool_pairs"]["tool_use_count"],
                          m["source_early_tool_pairs"]["tool_result_count"]), (52, 52))
        self.assertEqual(r["messages"][1:], h["messages"][88:])
        self.assertEqual({k: v for k, v in r.items() if k != "messages"},
                         {k: v for k, v in h.items() if k != "messages"})
        self.assertEqual(digest(canonical(h)), m["H_canonical_sha256"])

    def test_inverse_uses_only_rendered_request_text(self):
        h, r, m = project()
        rendered = r["messages"][0]["content"][0]["text"]
        self.assertTrue(rendered.startswith(PREFIX))
        actual = parse_rendered(rendered)
        expected = [(mi, bi, msg["role"], block)
                    for mi, msg in enumerate(h["messages"][:88])
                    for bi, block in enumerate(msg["content"])
                    if (msg["role"], block["type"]) in {
                        ("user", "text"), ("user", "tool_result"), ("assistant", "tool_use") }]
        self.assertEqual([(v["message_index"], v["block_index"], v["role"], v["block"])
                          for v in actual], expected)
        self.assertEqual(len(actual), 182)
        self.assertEqual(digest(rendered.encode()), m["rendered_history_sha256"])
        with self.assertRaises(RuntimeError):
            parse_rendered(rendered[:-2])

    def test_unknown_fields_fail_closed(self):
        h, _ = source_request()
        early = copy.deepcopy(h["messages"][:88])
        result = next(b for m in early for b in m["content"] if b["type"] == "tool_result")
        result["is_error"] = True
        with self.assertRaisesRegex(RuntimeError, "Unhandled block fields"):
            render(early)
        del result["is_error"]
        result["cache_control"] = {"type": "ephemeral"}
        with self.assertRaisesRegex(RuntimeError, "Unhandled block fields"):
            render(early)

    def test_no_semantic_selection_and_full_raw_result(self):
        h, r, manifest = project()
        original = [b["content"] for m in h["messages"][:88]
                    for b in m["content"] if b["type"] == "tool_result"]
        reconstructed = [v["block"]["content"] for v in parse_rendered(
            r["messages"][0]["content"][0]["text"])
                         if v["block"]["type"] == "tool_result"]
        self.assertEqual(reconstructed, original)
        self.assertEqual(sum(x["rule"] == "remove_early_assistant_thinking_or_free_text"
                             for x in manifest["blocks"]), 50)


if __name__ == "__main__":
    unittest.main()
