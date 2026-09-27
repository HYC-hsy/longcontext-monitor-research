"""Capture production provider-ready requests with a deterministic fake response.

This is an offline integration harness. It imports the existing Monitor Agent
and provider assembly, but replaces the transport boundary before any request
can leave the process.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
sys.path.insert(0, str(REPO / "GenericAgent-main"))

from monitor_agent_core.agent import MONITOR_TOOLS, MonitorAgent  # noqa: E402
from monitor_agent_core.provider import ModelResponse, MonitorProviderClient, ToolCall  # noqa: E402
from monitor_agent_core.working_context import current_working_context  # noqa: E402
from monitor_agent_core.workspace import MonitorWorkspace  # noqa: E402

from build_requests import M1_SYSTEM, _overlay  # noqa: E402


def _config() -> dict:
    return {
        "provider": "anthropic", "apikey": "offline-virtual-key",
        "apibase": "https://offline.invalid", "model": "claude-opus-4-8",
        "max_tokens": 1200, "temperature": 0, "max_retries": 0,
        "monitor_dcec": False, "monitor_semantic_continuity": True,
    }


def _responses():
    return [
        [{"type": "tool_use", "id": "w1", "name": "file_write",
          "input": {"path": "monitor/working.md", "content":
                     "Decision: reassess after the observed local change.\n",
                     "mode": "replace"}}],
        [{"type": "tool_use", "id": "wait1", "name": "wait",
          "input": {"after_turns": 1, "mode": "follow"}}],
        [{"type": "tool_use", "id": "i1", "name": "intervene",
          "input": {"message": "Recheck the current completion premise."}}],
        [{"type": "tool_use", "id": "wait2", "name": "wait",
          "input": {"after_turns": 1, "mode": "follow"}}],
        [{"type": "tool_use", "id": "a1", "name": "allow_complete", "input": {}}],
    ]


def run_condition(kind: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="rp-real-assembly-") as temp:
        root = Path(temp)
        evidence = root / "task"
        private = root / "monitor"
        (evidence / "workspace").mkdir(parents=True)
        (evidence / "original_task.txt").write_text(
            "Inspect the public task and determine whether the current work is ready.", encoding="utf-8")
        (evidence / "workspace" / "source.txt").write_text("public source", encoding="utf-8")
        private.mkdir()
        (private / "working.md").write_text(
            "Decision: assess completion.\nFocal uncertainty: local evidence scope.\n", encoding="utf-8")
        workspace = MonitorWorkspace(evidence, private)
        client = MonitorProviderClient("claude_monitor_opus48", _config())
        captured = []
        responses = _responses()

        def active_context():
            return current_working_context(workspace, limit=4000)

        client.prepare_active_context = active_context
        agent = MonitorAgent(client, workspace, max_review_turns=8)
        agent.system_prompt = M1_SYSTEM + ("\n\n" + _overlay("R_POLICY.txt") if kind == "R" else
                                            "\n\n" + _overlay("P_POLICY.txt") if kind == "P" else "")
        generation = {"value": 1}
        # The first wake has no pending root handoff, so wait is a real
        # terminal review action.  Later wakes install the same production
        # completion-state callback used by MonitorAgent.
        agent.completion_state = None
        intervention_events = []
        def intervention_callback(message):
            intervention_events.append(message)
            return {"accepted": True, "message": message}
        agent.intervention_callback = intervention_callback

        def fake_request_with_recovery(tools):
            url, headers, payload = client._anthropic_request(tools)
            # Provider payloads contain the live history list; snapshot bytes
            # at the send boundary so later turns cannot mutate the capture.
            captured.append({"url": url, "headers": dict(headers),
                             "payload": json.loads(json.dumps(payload, ensure_ascii=False))})
            if not responses:
                raise AssertionError("fake response script exhausted")
            return responses.pop(0), {"input_tokens": 1, "output_tokens": 1}

        client._request_with_recovery = fake_request_with_recovery
        first = agent.review(
            "Initial public event. Original task: Inspect the public task and determine whether the current work is ready.",
            completion_pending=False)
        assert first.kind == "wait"
        assert len(captured) == 2
        # The second request must contain the new working state and prior tool result.
        assert "reassess after" in json.dumps(captured[1]["payload"], ensure_ascii=False)
        assert any("tool_result" in json.dumps(message) for message in client.history)

        agent.completion_state = lambda: {"generation": generation["value"], "request_id": "root-1", "cursor": 1}
        second = agent.review("New public event after wait.", completion_pending=True)
        assert second.kind == "wait"
        assert intervention_events == ["Recheck the current completion premise."]
        generation["value"] = 2
        third = agent.review("A new completion proposal is now current.", completion_pending=True)
        assert third.kind == "allow_complete"
        assert len(captured) == 5
        assert len(MONITOR_TOOLS) == 7
        # Verify the actual provider-ready payload, rather than a simplified
        # request envelope: task evidence, current working state, tool
        # results, and the production seven-tool schemas are all present.
        first_text = json.dumps(captured[0]["payload"]["messages"], ensure_ascii=False)
        second_text = json.dumps(captured[1]["payload"]["messages"], ensure_ascii=False)
        assert "public task" in first_text
        assert "Decision: assess completion." in first_text, first_text
        assert "reassess after" in second_text
        assert "tool_result" in second_text
        return {
            "condition": kind,
            "provider_ready_requests": len(captured),
            "tool_schema_count": len(captured[0]["payload"]["tools"]),
            "first_request_system_sha256": __import__("hashlib").sha256(
                captured[0]["payload"]["system"].encode()).hexdigest(),
            "working_state_visible_on_second_request": True,
            "wait_then_new_review": True,
            "intervene_invalidated_old_completion": bool(intervention_events),
            "new_allow_complete_accepted": True,
            "actual_tool_schema": captured[0]["payload"]["tools"],
            "request_payloads": captured,
            "transport_calls": 0,
        }


if __name__ == "__main__":
    reports = [run_condition(kind) for kind in ("M1", "R", "P")]
    capture = {report["condition"]: report.pop("request_payloads") for report in reports}
    (ROOT / "integration_capture.json").write_text(
        json.dumps(capture, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "integration_report.json").write_text(
        json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(reports, indent=2, ensure_ascii=False))
