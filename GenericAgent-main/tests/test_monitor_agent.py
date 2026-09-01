import json
from types import SimpleNamespace

import pytest

from agent_loop import exhaust
from monitor_agent import MONITOR_TOOLS, MonitorAgent, MonitorWorkspace
from llmcore import NativeToolClient, ToolClient


class ToolCall:
    def __init__(self, name, arguments, call_id="call"):
        self.function = SimpleNamespace(name=name, arguments=json.dumps(arguments))
        self.id = call_id


class Response:
    def __init__(self, tool_name, arguments, content=""):
        self.content = content
        self.thinking = ""
        self.stop_reason = "tool_use"
        self.tool_calls = [ToolCall(tool_name, arguments)]


class PersistentSequenceClient:
    """Minimal stand-in for a provider session that persists across wakes."""

    def __init__(self, responses):
        self.responses = iter(responses)
        self.last_tools = ""
        self.calls = []
        self.provider_history = []

    def chat(self, messages, tools):
        self.calls.append({"messages": messages, "tools": tools})
        self.provider_history.extend(messages)
        if False:
            yield None
        response = next(self.responses)
        self.provider_history.append({"role": "assistant", "content": response.content})
        return response


@pytest.fixture
def roots(tmp_path):
    task = tmp_path / "task"
    private = tmp_path / "monitor"
    task.mkdir()
    (task / "task.txt").write_text("Preserve the literal wildcard.\n", encoding="utf-8")
    return task, private


def test_tool_surface_is_small_and_has_no_task_mutation_tool():
    names = [tool["function"]["name"] for tool in MONITOR_TOOLS]
    assert names == [
        "file_read", "file_write", "file_patch", "code_run",
        "wait", "intervene", "allow_complete",
    ]
    assert "task_write" not in names


def test_monitor_role_does_not_inherit_ga_executor_memory_protocol():
    backend = SimpleNamespace(name="fake", system="")
    native = NativeToolClient(backend)
    native.set_role("monitor")
    native.set_system("monitor system")
    assert backend.system == "monitor system"
    assert "summary" not in backend.system.lower()

    text_client = ToolClient(backend)
    text_client.set_role("monitor")
    instruction = text_client._prepare_tool_instruction(MONITOR_TOOLS)
    assert "long-term working memory" not in instruction
    assert "<summary>" not in instruction
    assert "<tool_use>" in instruction


def test_monitor_can_inspect_then_intervene_in_one_review(roots):
    task, private = roots
    client = PersistentSequenceClient([
        Response("file_read", {"path": "task/task.txt"}),
        Response("intervene", {"message": "Keep the literal wildcard; the current intent drops it."}),
    ])
    agent = MonitorAgent(client, MonitorWorkspace(task, private))

    action = exhaust(agent.review("Turn 3 intent may narrow the wildcard."))

    assert action.kind == "intervene"
    assert "literal wildcard" in action.payload["message"]
    assert len(client.calls) == 2
    assert client.calls[1]["messages"][0]["content"] == "Continue the same review and finish with one control action."
    assert client.calls[1]["messages"][0]["tool_results"][0]["content"]


def test_same_monitor_client_and_history_survive_multiple_wakes(roots):
    task, private = roots
    client = PersistentSequenceClient([
        Response("wait", {"after_turns": 4}),
        Response("wait", {"after_turns": 1}),
    ])
    agent = MonitorAgent(client, MonitorWorkspace(task, private))

    first = exhaust(agent.review("Initialize from the root task."))
    second = exhaust(agent.review("Cursor advanced from 0 to 4."))

    assert first.payload == {"after_turns": 4}
    assert second.payload == {"after_turns": 1}
    assert len(client.calls) == 2
    assert len(client.provider_history) == 6
    assert client.calls[0]["messages"][1]["content"] == "Initialize from the root task."
    assert client.calls[1]["messages"][1]["content"] == "Cursor advanced from 0 to 4."
    audit_lines = (private / "audit" / "reviews.jsonl").read_text(encoding="utf-8").splitlines()
    audit = [json.loads(line) for line in audit_lines]
    assert len(audit) == 2
    assert audit[1]["history_before"]["items"] == audit[0]["history_after"]["items"]
    assert audit[1]["history_after"]["items"] > audit[1]["history_before"]["items"]
    assert audit[1]["action"]["kind"] == "wait"


def test_allow_complete_is_rejected_outside_completion_review(roots):
    task, private = roots
    client = PersistentSequenceClient([
        Response("allow_complete", {}),
        Response("wait", {"after_turns": 2}),
    ])
    agent = MonitorAgent(client, MonitorWorkspace(task, private))

    action = exhaust(agent.review("Ordinary patrol wake."))

    assert action.kind == "wait"
    error = client.calls[1]["messages"][0]["tool_results"][0]["content"]
    assert "No root completion is pending" in error


def test_allow_complete_is_available_at_root_boundary(roots):
    task, private = roots
    client = PersistentSequenceClient([Response("allow_complete", {})])
    agent = MonitorAgent(client, MonitorWorkspace(task, private))

    action = exhaust(agent.review("The Task Agent proposes root completion.", completion_pending=True))

    assert action.kind == "allow_complete"


def test_code_run_uses_disposable_task_copy(roots):
    task, private = roots
    script = "from pathlib import Path\np=Path('.task_view/task.txt')\np.write_text('tampered')\nprint(p.read_text())"
    client = PersistentSequenceClient([
        Response("code_run", {"code": script, "type": "python"}),
        Response("wait", {"after_turns": 1}),
    ])
    agent = MonitorAgent(client, MonitorWorkspace(task, private))

    action = exhaust(agent.review("Inspect the task with analysis code."))

    assert action.kind == "wait"
    assert (task / "task.txt").read_text(encoding="utf-8") == "Preserve the literal wildcard.\n"
    assert (private / ".task_view" / "task.txt").read_text(encoding="utf-8") == "tampered"
