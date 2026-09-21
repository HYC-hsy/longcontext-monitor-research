from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "GenericAgent-main"))
sys.path.insert(0, str(ROOT / "method_discovery"))

import dcec_transport_smoke_worker as worker
import run_dcec_transport_smoke as runner


class FakeResponse:
    def __init__(self, status_code=200, lines=()):
        self.status_code = status_code
        self._lines = list(lines)
        self.text = "upstream failure" if status_code >= 400 else ""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def iter_lines(self):
        return iter(self._lines)

    def json(self):
        return {"error": {"type": "upstream_error"}}

    def close(self):
        return None


def config():
    return {
        "provider": "anthropic", "apikey": "isolated-local-channel",
        "apibase": "http://127.0.0.1:18765", "model": "claude-opus-4-8",
        "max_tokens": 32, "max_retries": 0, "transport_route": "monitor",
    }


def anthropic_stream(text="TRANSPORT_OK"):
    events = [
        {"type": "message_start", "message": {"id": "msg_test", "usage": {"input_tokens": 3}}},
        {"type": "content_block_start", "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": text}},
        {"type": "content_block_stop"},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 2}},
        {"type": "message_stop"},
    ]
    return [("data: " + json.dumps(item)).encode() for item in events]


def test_fake_success_stream_uses_production_parser_once(monkeypatch):
    calls = []
    monkeypatch.setattr("monitor_agent_core.provider.requests.post",
                        lambda *args, **kwargs: calls.append((args, kwargs)) or FakeResponse(lines=anthropic_stream()))
    result = worker.perform_smoke(config(), "Return exactly: TRANSPORT_OK", "TRANSPORT_OK")
    assert len(calls) == 1
    assert result["logical_calls"] == result["provider_attempts"] == 1
    assert result["stream_complete"] is True
    assert result["final_text"] == "TRANSPORT_OK"
    assert result["exact_text_match"] is True
    assert result["tool_calls"] == 0


def test_fake_502_has_no_second_request(monkeypatch):
    calls = []
    monkeypatch.setattr("monitor_agent_core.provider.requests.post",
                        lambda *args, **kwargs: calls.append((args, kwargs)) or FakeResponse(status_code=502))
    result = worker.perform_smoke(config(), "smoke", "TRANSPORT_OK")
    assert len(calls) == 1
    assert result["logical_calls"] == result["provider_attempts"] == 1
    assert result["status"] == "transport_error"
    assert result["stream_complete"] is False


def test_unauthorized_manifest_stops_before_any_execution(monkeypatch, tmp_path):
    manifest = json.loads(runner.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["execution_authorized"] is False
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    called = []
    monkeypatch.setattr(runner, "_run_isolated", lambda *args, **kwargs: called.append(True))
    with pytest.raises(PermissionError, match="zero provider requests"):
        runner.execute(path, runner.FROZEN_OUTPUT, tmp_path / "missing-config.json")
    assert called == []
    assert not runner.FROZEN_OUTPUT.exists()


def test_output_path_is_frozen_and_existing_output_is_rejected(tmp_path):
    frozen = tmp_path / "frozen"
    with pytest.raises(ValueError, match="frozen path"):
        runner.validate_output(tmp_path / "other", frozen)
    frozen.mkdir()
    with pytest.raises(FileExistsError, match="already exists"):
        runner.validate_output(frozen, frozen)


def test_materialized_smoke_runtime_disables_dcec_and_omits_fixture(tmp_path):
    manifest = json.loads(runner.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    destination = tmp_path / "source"
    runner._prepare_source(destination, config(), manifest)
    smoke = json.loads((destination / "smoke_config.json").read_text(encoding="utf-8"))
    assert smoke["dcec_enabled"] is False
    assert smoke["scientific_fixture_used"] is False
    assert smoke["provider_config"]["max_retries"] == 0
    assert not any(path.name in {"fixture_spec.json", "discriminating_manifest.json"}
                   for path in destination.rglob("*"))


def test_manifest_freezes_one_call_one_request_and_output():
    manifest = json.loads(runner.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["max_logical_calls"] == 1
    assert manifest["max_provider_requests"] == 1
    assert manifest["transport_retries"] == 0
    assert manifest["dcec_enabled"] is False
    assert manifest["scientific_fixture_used"] is False
    assert manifest["execution_output"] == "method_discovery/runs/dcec_v0_infra_smoke_r1"


def test_authorized_copy_passes_frozen_source_identity_check():
    manifest = json.loads(runner.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    manifest["execution_authorized"] = True
    runner.validate_manifest(manifest, runner.DEFAULT_MANIFEST)
