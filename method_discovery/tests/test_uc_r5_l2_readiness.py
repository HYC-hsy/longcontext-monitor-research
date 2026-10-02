"""Offline-only checks for deployed scripted worker evidence."""

import importlib.util
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "method_discovery/runs/uc_r5_cmp_readiness_20261003"
SCRIPT = ROOT / "method_discovery/uc_r5_l2_archive.py"
SPEC = importlib.util.spec_from_file_location("uc_r5_l2_archive", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_deployed_worker_five_conditions_and_guard():
    expected = {"C0": ("off", "off", 2), "RP": ("flat", "note", 3),
                "AP": ("framed", "note", 3), "RB": ("flat", "routed", 3),
                "AB": ("framed", "routed", 3)}
    for group, (view, intent, calls) in expected.items():
        root = OUT / "L2" / group
        summary = json.loads((root / "research_l2_summary.json").read_text())
        guard = json.loads((root / "monitor_private/audit/research_send_guard.json").read_text())
        folder = root / "monitor_private/audit/research_provider_ready"
        requests = sorted(folder.glob("request-*.json"))
        assert (summary["view"], summary["intent"]) == (view, intent)
        assert len(requests) == calls
        assert summary["input_readback_equal"]
        assert summary["observed_model"] is None and summary["real_model_requests"] == 0
        assert summary["root_control"] == "ALLOW_COMPLETE"
        assert guard["guard_installed_in_worker"] and guard["guard_exercised_in_worker"]
        assert not guard["gateway_mount_present"] and not guard["gateway_socket_present"]
        assert guard["worker_pid"] != guard["parent_pid"]
        first = json.loads(requests[0].read_text(encoding="utf-8"))
        last = json.loads(requests[-1].read_text(encoding="utf-8"))
        assert first["root_handoff"] is None and last["root_handoff"] is not None
        if group != "C0":
            middle = json.loads(requests[1].read_text(encoding="utf-8"))
            text = json.dumps(middle, ensure_ascii=False)
            assert "go.mod" in text and "Inspect current public source" in text


def test_c0_frozen_provider_ready_equality():
    comparison = json.loads((OUT / "L2_EVIDENCE/C0_BASELINE_COMPARISON.json").read_text())
    assert comparison["all_equal"]
    assert len(comparison["requests"]) == 2
    assert all(row["candidate_normalized_sha256"] == row["baseline_normalized_sha256"]
               for row in comparison["requests"])


def test_l2_archive_recomputes_every_full_request_hash():
    archive = OUT / "L2_EVIDENCE"
    manifest = json.loads((archive / "MANIFEST.json").read_text())
    for group, detail in manifest.items():
        for row in detail["archived_files"]:
            data = (archive / group / row["path"]).read_bytes()
            assert len(data) == row["bytes"]
            assert MODULE.digest(data) == row["sha256"]
        assert detail["local_unuploaded_root_checkpoint"]["total_bytes"] >= 0


def test_uploaded_requests_exclude_credential_markers():
    archive = OUT / "L2_EVIDENCE"
    for request in archive.glob("*/monitor_private/audit/research_provider_ready/request-*.json"):
        body = request.read_text(encoding="utf-8")
        assert not re.search(r"authorization|bearer\s+\S+|api[_-]?key|sk-[A-Za-z0-9]{12}",
                             body, flags=re.IGNORECASE)


def test_staged_slots_remain_unstarted():
    slots = json.loads((OUT / "SLOT_DRAFT.json").read_text())["slots"]
    assert len(slots) == 30
    assert all(row["status"] == "not_started" for row in slots)
    draft = json.loads((OUT / "PREREGISTRATION_DRAFT.json").read_text())
    assert draft["execution_authorized"] is False


def test_request_normalization_only_mechanical_identity():
    sample = {"review_id": "abcdef", "messages": [{"text":
        "task original /app/.monitor_original_task_" + "a" * 32 +
        ".txt; root /probe/C0/task_evidence"}], "system": "semantic-content"}
    normalized = MODULE.normalized_request(sample)
    assert normalized["review_id"] == "<REVIEW_ID>"
    assert "/probe/<GROUP>/" in normalized["messages"][0]["text"]
    assert "semantic-content" == normalized["system"]
