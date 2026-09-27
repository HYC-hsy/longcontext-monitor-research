"""Deterministic no-provider checks for R/P prototype isolation and wiring."""

import hashlib
import json
import re
from pathlib import Path

from build_requests import assert_invariants
from real_request_harness import run_condition

ROOT = Path(__file__).resolve().parent


def main() -> None:
    report = assert_invariants()
    assert {"M1_vs_R", "M1_vs_P", "adversarial_checks"} <= set(report)
    assert report["M1_vs_R"]["system_suffix_only"]
    assert report["M1_vs_P"]["system_suffix_only"]
    captures = {}
    integration = []
    for kind in ("M1", "R", "P"):
        item = run_condition(kind)
        captures[kind] = item.pop("request_payloads")
        integration.append(item)
        assert item["transport_calls"] == 0
        assert item["tool_schema_count"] == 7
    schema_hashes = {
        kind: hashlib.sha256(json.dumps(captures[kind][0]["payload"]["tools"],
                                         sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        for kind in captures
    }
    assert len(set(schema_hashes.values())) == 1
    def normalized_request(request):
        raw = json.dumps(request["payload"], ensure_ascii=False, sort_keys=True)
        raw = re.sub(r"(?:[A-Za-z]:)?[/\\]+Users[/\\]+[^\" ]+[/\\]+Temp[/\\]+rp-real-assembly-[^/\\\"]+",
                     "<record-local-temp>", raw)
        value = json.loads(raw)
        value.pop("system", None)
        return value
    for index in range(5):
        assert normalized_request(captures["M1"][index]) == normalized_request(captures["R"][index])
        assert normalized_request(captures["M1"][index]) == normalized_request(captures["P"][index])
    # The research condition is never model-visible; only neutral strategy
    # prose differs from M1.  The actual production payload is checked here,
    # not a simplified envelope.
    for kind, requests in captures.items():
        joined = json.dumps(requests, ensure_ascii=False)
        assert "planned R treatment difference" not in joined
        assert "planned P treatment difference" not in joined
        assert "research_metadata" not in joined
    assert "R_POLICY" not in json.dumps(captures["R"], ensure_ascii=False)
    assert "P_POLICY" not in json.dumps(captures["P"], ensure_ascii=False)
    (ROOT / "integration_capture.json").write_text(
        json.dumps(captures, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "integration_report.json").write_text(
        json.dumps({"summary": integration, "tool_schema_sha256": schema_hashes,
                    "provider_calls": 0}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("offline_checks: PASS (provider_calls=0, production_changes=0, real_assembly=3 conditions)")


if __name__ == "__main__":
    main()
