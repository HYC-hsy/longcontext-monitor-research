"""Offline protocol-only replay; never edits the archived provider response."""

import hashlib
import json
from pathlib import Path
import unittest

from .audit import validate_audit_result, validate_audit_result_v1
from .source import ContractError, SourceCatalog


ROOT = Path(__file__).parent / "evidence" / "live_diagnostic_v3" / "visible_exchange"
RAW_SHA256 = "74ce3fde512db0445cff8a00d4b108dd5da8f20d317400b710118375c7ff72e6"


class HistoricalResponseProtocolReplay(unittest.TestCase):
    def test_reaudit_synthetic_v2_is_not_a_new_model_response(self):
        raw = (ROOT / "04_audit_visible_response.txt").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), RAW_SHA256)
        self.assertTrue(raw.startswith(b"```json\n") and raw.endswith(b"\n```"))
        original = json.loads(raw[8:-4])
        view = json.loads((ROOT / "04_audit_parsed_user_view.json").read_text(
            encoding="utf-8"))
        self.assertEqual(original["protocol"], "audit-result/1")
        self.assertEqual(len(original["coverage"]), 15)
        # Historical v1 still rejects the actual response, exactly as archived.
        with self.assertRaisesRegex(ContractError, "coverage_mismatch"):
            validate_audit_result_v1(original, view=view,
                                     catalog=SourceCatalog({}, "historical"))
        synthetic = {key: value for key, value in original.items()
                     if key != "coverage"}
        synthetic["protocol"] = "audit-result/2"
        self.assertEqual(set(original) - set(synthetic), {"coverage"})
        self.assertEqual({key: value for key, value in synthetic.items()
                          if key != "protocol"},
                         {key: value for key, value in original.items()
                          if key != "protocol" and key != "coverage"})
        self.assertEqual(validate_audit_result(synthetic, view=view,
                         catalog=SourceCatalog({}, "synthetic"))["outcome"], "clean")
        with self.assertRaises(ContractError):
            validate_audit_result(original, view=view,
                                  catalog=SourceCatalog({}, "historical"))


if __name__ == "__main__":
    unittest.main()
