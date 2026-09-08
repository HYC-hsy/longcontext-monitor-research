import json
import threading
import time
from types import SimpleNamespace

from manual_completion_boundary import ManualCompletionBoundary
from manual_completion_boundary import ManualInterventionInbox
from task_interruption import ResumableInterruption


def test_inbox_interrupts_without_waiting_for_agent_boundary(tmp_path):
    mailbox = ResumableInterruption()
    interrupted = threading.Event()
    def interrupt(message):
        request = mailbox.request(message)
        interrupted.set()
        return request
    inbox = ManualInterventionInbox(tmp_path, interrupt, poll_seconds=0.01).start()
    try:
        pending = inbox.inbox / "001.tmp"
        pending.write_text("Recheck the test against the original requirement.", encoding="utf-8")
        pending.rename(inbox.inbox / "001.txt")
        assert interrupted.wait(2), "No Agent event is needed to deliver the input"
    finally:
        inbox.close()
    assert not inbox.thread.is_alive()
    assert len(mailbox.consume()) == 1
    assert mailbox.consume() == []
    receipt = json.loads((tmp_path / "receipts.jsonl").read_text(encoding="utf-8"))
    assert receipt["status"] == "interruption_requested"
    assert receipt["request"]["sequence"] == 1


def test_inbox_failed_delivery_is_archived_not_repeated(tmp_path):
    def fail(message):
        raise RuntimeError("cancel transport failed")
    inbox = ManualInterventionInbox(tmp_path, fail)
    inbox.inbox.mkdir(parents=True)
    inbox.archive.mkdir()
    (inbox.inbox / "001.txt").write_text("correction", encoding="utf-8")
    inbox.poll_once()
    inbox.poll_once()
    receipts = (tmp_path / "receipts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(receipts) == 1
    assert json.loads(receipts[0])["status"] == "delivery_failed"


def test_inbox_rejects_cross_task_reuse(tmp_path):
    import pytest
    inbox = ManualInterventionInbox(tmp_path, lambda message: None)
    inbox.inbox.mkdir(parents=True)
    (inbox.inbox / "old.txt").write_text("previous task", encoding="utf-8")
    with pytest.raises(ValueError, match="fresh"):
        inbox.start()


def test_external_input_uses_real_ga_cancel_and_same_loop_resume(tmp_path):
    # Load only this method: importing agentmain would load credentials/GUI state.
    import ast
    from pathlib import Path
    from test_task_interruption import Parent, Handler, Response
    from agent_loop import agent_runner_loop, exhaust
    import llmcore
    module = ast.parse((Path(__file__).parents[1] / "agentmain.py").read_text(encoding="utf-8"))
    agent = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "GenericAgent")
    method = next(n for n in agent.body if isinstance(n, ast.FunctionDef) and n.name == "request_monitor_interruption")
    namespace = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "agentmain.py", "exec"), namespace)
    parent = Parent()
    handler = Handler(parent)
    parent.handler = handler
    cancelled = threading.Event()
    parent.llmclient = SimpleNamespace(backend=SimpleNamespace(cancel_active_response=cancelled.set))
    inbox = ManualInterventionInbox(
        tmp_path, lambda message: namespace[method.name](parent, message), poll_seconds=0.01
    ).start()
    class Client:
        last_tools = ""
        def __init__(self): self.calls = []
        def chat(self, messages, tools):
            self.calls.append(messages)
            if len(self.calls) == 1:
                pending = inbox.inbox / "001.tmp"
                pending.write_text("Preserve the original API order.", encoding="utf-8")
                pending.rename(inbox.inbox / "001.txt")
                assert cancelled.wait(2)
                assert handler.code_stop_signal
                raise llmcore.ProviderResponseCancelled("human interruption")
            if False: yield None
            return Response()
    client = Client()
    try:
        result = exhaust(agent_runner_loop(client, "system", "task", handler, [], max_turns=3, verbose=False))
    finally:
        inbox.close()
    assert result["result"] == "EXITED"
    assert "Preserve the original API order." in client.calls[1][-1]["content"]


def test_manual_boundary_receives_continue_decision(tmp_path):
    proposal = SimpleNamespace(
        proposal_id="proposal-test",
        as_payload=lambda: {"proposal_id": "proposal-test", "response_preview": "done"},
    )
    boundary = ManualCompletionBoundary(tmp_path, timeout_seconds=2, poll_seconds=0.01)
    result = {}

    thread = threading.Thread(
        target=lambda: result.setdefault("decision", boundary(proposal, 9, None))
    )
    thread.start()
    proposal_path = tmp_path / "proposal_proposal-test.json"
    for _ in range(100):
        if proposal_path.exists():
            break
        time.sleep(0.01)
    (tmp_path / "decision_proposal-test.json").write_text(json.dumps({
        "decision": "CONTINUE",
        "reason_codes": ["HUMAN_FOUND_OPEN_WORK"],
        "next_prompt": "Reconcile the remaining target.",
    }), encoding="utf-8")
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert result["decision"].decision == "CONTINUE"
    assert result["decision"].next_prompt == "Reconcile the remaining target."


def test_manual_boundary_times_out_closed(tmp_path):
    proposal = SimpleNamespace(
        proposal_id="proposal-timeout",
        as_payload=lambda: {"proposal_id": "proposal-timeout"},
    )
    decision = ManualCompletionBoundary(
        tmp_path, timeout_seconds=0.01, poll_seconds=0.001
    )(proposal, 3, None)
    assert decision.decision == "ABSTAIN"
    assert decision.reason_codes == ("MANUAL_DECISION_TIMEOUT",)


def _resolve_decision(tmp_path, proposal_id, payload):
    proposal = SimpleNamespace(
        proposal_id=proposal_id,
        as_payload=lambda: {"proposal_id": proposal_id},
    )
    boundary = ManualCompletionBoundary(tmp_path, timeout_seconds=2, poll_seconds=0.01)
    result = {}
    thread = threading.Thread(
        target=lambda: result.setdefault("decision", boundary(proposal, 5, None))
    )
    thread.start()
    proposal_path = tmp_path / f"proposal_{proposal_id}.json"
    for _ in range(100):
        if proposal_path.exists():
            break
        time.sleep(0.01)
    (tmp_path / f"decision_{proposal_id}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    thread.join(timeout=2)
    assert not thread.is_alive()
    return result["decision"]


def test_manual_boundary_accepts_message_as_continue_prompt(tmp_path):
    decision = _resolve_decision(tmp_path, "proposal-message", {
        "decision": "CONTINUE",
        "message": "Reopen the timer obligation and rerun the exact test.",
    })
    assert decision.decision == "CONTINUE"
    assert decision.next_prompt == "Reopen the timer obligation and rerun the exact test."


def test_manual_boundary_rejects_continue_without_prompt(tmp_path):
    decision = _resolve_decision(tmp_path, "proposal-empty", {
        "decision": "CONTINUE",
        "message": "   ",
    })
    assert decision.decision == "ABSTAIN"
    assert decision.reason_codes == ("MANUAL_CONTINUE_PROMPT_MISSING",)
    assert decision.next_prompt is None
