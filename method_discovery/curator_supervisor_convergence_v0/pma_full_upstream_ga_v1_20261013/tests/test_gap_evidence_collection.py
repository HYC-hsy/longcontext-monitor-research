"""A hash-bearing evidence bank must not be silently rewritten for publication."""

import json
import unittest

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.collect_single_run_fixture import (
    _verifiable_evidence_snapshot, _verifiable_evidence_jsonl,
)


class EvidenceCollectionTests(unittest.TestCase):
    def test_preserves_nested_json_identity_bytes(self):
        source_id = json.dumps(["run", "public", "task", "initial_user_content"],
                               separators=(",", ":"))
        raw = json.dumps({"source_id": source_id}, separators=(",", ":")).encode()
        shown, removed = _verifiable_evidence_snapshot(raw, [])
        self.assertEqual(shown, raw)
        self.assertEqual(removed, 0)

    def test_rejects_snapshot_needing_redaction(self):
        for value in ({"source_id": "private-token-value"},
                      {"thinking": "hidden reasoning"},
                      {"source_id": "https://private.example/test"}):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "cannot retain its binding"):
                    _verifiable_evidence_snapshot(json.dumps(value).encode(),
                                                  ["private-token-value"])

    def test_sealed_jsonl_preserves_nested_identity_bytes(self):
        source_id = json.dumps(["run", "public", "task", "content"],
                               separators=(",", ":"))
        raw = (json.dumps({"source_id": source_id}) + "\n").encode()
        self.assertEqual(_verifiable_evidence_jsonl(raw, []), (raw, 0))

    def test_sealed_jsonl_rejects_private_or_hidden_content(self):
        for value in ({"source_id": "private-token-value"},
                      {"thinking": "hidden reasoning"},
                      {"metadata": {"private": "value"}},
                      {"prompt": "https://private.example/secret"}):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "needs redaction"):
                    _verifiable_evidence_jsonl((json.dumps(value) + "\n").encode(),
                                               ["private-token-value"])

    def test_sealed_jsonl_allows_only_inert_fixture_fields(self):
        raw = (json.dumps({"metadata": {},
            "prompt": "fixture at http://127.0.0.1:19173/"}) + "\n").encode()
        self.assertEqual(_verifiable_evidence_jsonl(raw, []), (raw, 0))


if __name__ == '__main__':
    unittest.main()
