"""Offline checks of the existing Task transport's retry-count meaning."""

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import requests


sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "GenericAgent-main"))
import llmcore  # noqa: E402


class _Response:
    status_code = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _session(retries):
    return SimpleNamespace(max_retries=retries, stream=True, connect_timeout=1,
                           read_timeout=1, proxies=None, verify=True,
                           research_capture_payload=False)


def _complete_response(_):
    if False:
        yield None
    return [{"type": "text", "text": "complete"}]


def test_task_four_retries_means_five_possible_attempts(monkeypatch):
    attempts = []

    def fake_post(*_args, **_kwargs):
        attempts.append(len(attempts) + 1)
        if len(attempts) <= 4:
            raise requests.ConnectionError("fixture connection failure")
        return _Response()

    monkeypatch.setattr(llmcore.requests, "post", fake_post)
    monkeypatch.setattr(llmcore.time, "sleep", lambda _seconds: None)
    result = list(llmcore._stream_with_retry(
        _session(4), "https://fixture.invalid/messages", {}, {"model": "fixture"},
        _complete_response,
    ))
    assert result == []
    assert attempts == [1, 2, 3, 4, 5]


def test_zero_ambiguous_retries_means_one_attempt(monkeypatch):
    attempts = []

    def fake_post(*_args, **_kwargs):
        attempts.append(len(attempts) + 1)
        raise requests.ConnectionError("fixture connection failure")

    monkeypatch.setattr(llmcore.requests, "post", fake_post)
    monkeypatch.setattr(llmcore.time, "sleep", lambda _seconds: None)
    result = list(llmcore._stream_with_retry(
        _session(0), "https://fixture.invalid/messages", {}, {"model": "fixture"},
        _complete_response,
    ))
    assert attempts == [1]
    assert len(result) == 1 and "ConnectionError" in result[0]


def test_harbor_wrapper_freezes_zero_whole_trial_retries():
    source = (Path(__file__).resolve().parents[3] / "long_context_bench" /
              "scripts" / "run_ultralong_m12_proofs.py")
    if not source.exists():
        pytest.skip("external Harbor wrapper is absent from this research worktree")
    text = source.read_text(encoding="utf-8")
    assert '"--max-retries",\n        "0"' in text
