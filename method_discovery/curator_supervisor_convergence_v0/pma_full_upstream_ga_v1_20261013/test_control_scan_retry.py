"""Bounded Docker-exec recovery without weakening process registration."""

import json
import subprocess
from unittest.mock import patch

import pytest

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.control_processes import scan


def _result(code, payload=""):
    return subprocess.CompletedProcess([], code, payload, "transient Docker error")


def test_single_exec_failure_requires_fresh_successful_scan():
    payload = json.dumps({"pid_namespace": "pid:[1]", "processes": [{"pid": 7}]})
    with patch("subprocess.run", side_effect=[_result(1), _result(0, payload)]) as run, \
         patch("time.sleep") as sleep:
        result = scan("container", "python", "run")
    assert result["processes"] == [{"pid": 7}]
    assert run.call_count == 2
    sleep.assert_called_once_with(0.25)


def test_persistent_exec_failure_still_fails_closed():
    with patch("subprocess.run", side_effect=[_result(125)] * 3) as run, \
         patch("time.sleep") as sleep:
        with pytest.raises(RuntimeError, match=r"docker exit 125"):
            scan("container", "python", "run")
    assert run.call_count == 3
    assert sleep.call_count == 2


def test_malformed_success_is_not_silently_retried_or_accepted():
    with patch("subprocess.run", return_value=_result(0, "{}")) as run:
        with pytest.raises(RuntimeError, match="malformed"):
            scan("container", "python", "run")
    run.assert_called_once()
