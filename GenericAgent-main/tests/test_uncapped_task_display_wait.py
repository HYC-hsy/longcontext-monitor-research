"""The CLI display drain must not cap an uncapped task's quiet tool time."""

import ast
import os
import queue
from pathlib import Path

import pytest


def _wait_function():
    source = Path(__file__).parents[1] / "agentmain.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_next_task_display_item"
    )
    namespace = {"os": os, "queue": queue}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[function.name]


class _DisplayQueue:
    def __init__(self, empty_polls=0):
        self.empty_polls = empty_polls
        self.timeouts = []

    def get(self, timeout):
        self.timeouts.append(timeout)
        if self.empty_polls:
            self.empty_polls -= 1
            raise queue.Empty
        return {"done": "complete"}


class _Thread:
    def __init__(self, alive):
        self.alive = alive

    def is_alive(self):
        return self.alive


def test_uncapped_wait_survives_quiet_polls(monkeypatch):
    monkeypatch.setenv("GA_EXPERIMENT_RUNTIME_POLICY", "v1")
    monkeypatch.setenv("GA_EXPERIMENT_TASK_TURNS", "uncapped")
    display = _DisplayQueue(empty_polls=4)
    assert _wait_function()(display, _Thread(True)) == {"done": "complete"}
    assert display.timeouts == [5] * 5


def test_uncapped_wait_detects_dead_worker(monkeypatch):
    monkeypatch.setenv("GA_EXPERIMENT_RUNTIME_POLICY", "v1")
    monkeypatch.setenv("GA_EXPERIMENT_TASK_TURNS", "uncapped")
    with pytest.raises(RuntimeError, match="thread exited"):
        _wait_function()(_DisplayQueue(empty_polls=1), _Thread(False))


def test_finite_policy_keeps_existing_timeout(monkeypatch):
    monkeypatch.setenv("GA_EXPERIMENT_RUNTIME_POLICY", "v1")
    monkeypatch.setenv("GA_EXPERIMENT_TASK_TURNS", "300")
    display = _DisplayQueue()
    assert _wait_function()(display, _Thread(True)) == {"done": "complete"}
    assert display.timeouts == [2200]
