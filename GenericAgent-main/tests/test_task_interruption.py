from types import SimpleNamespace

import pytest

import llmcore
from agent_loop import BaseHandler, StepOutcome, agent_runner_loop, exhaust
from task_interruption import ResumableInterruption


class Parent:
    def __init__(self):
        self.task_dir = None
        self.research_condition = None
        self.resumable_interruption = ResumableInterruption()

    def request(self, message):
        return self.resumable_interruption.request(message)

    def consume_resumable_interruption(self):
        return self.resumable_interruption.consume()


class Handler(BaseHandler):
    def __init__(self, parent):
        self.parent = parent
        self._done_hooks = []
        self.code_stop_signal = []

    def do_no_tool(self, args, response):
        return StepOutcome(response.content, should_exit=True)


class Response:
    content = "continued correctly"
    thinking = ""
    stop_reason = "end_turn"
    tool_calls = []


class ToolCallResponse(Response):
    def __init__(self):
        self.content = "<summary>About to apply the narrowing patch</summary>"
        self.tool_calls = [SimpleNamespace(
            id="dangerous-call",
            function=SimpleNamespace(name="dangerous_tool", arguments="{}"),
        )]


class InterruptThenContinueClient:
    last_tools = ""

    def __init__(self, parent):
        self.parent = parent
        self.calls = []

    def chat(self, messages, tools):
        self.calls.append(messages)
        if len(self.calls) == 1:
            self.parent.request("The current intent violates the literal wildcard requirement.")
            if False:
                yield None
            raise llmcore.ProviderResponseCancelled("cancelled")
        if False:
            yield None
        return Response()


def test_resumable_interruption_is_ordered_and_consumed_once():
    mailbox = ResumableInterruption()
    mailbox.request("first")
    mailbox.request("second")

    assert mailbox.is_requested()
    assert [item["message"] for item in mailbox.consume()] == ["first", "second"]
    assert not mailbox.is_requested()
    assert mailbox.consume() == []


def test_agent_loop_cancels_current_response_and_resumes_same_loop():
    parent = Parent()
    handler = Handler(parent)
    client = InterruptThenContinueClient(parent)

    result = exhaust(agent_runner_loop(
        client, "system", "root task", handler, [], max_turns=3, verbose=False
    ))

    assert result["result"] == "EXITED"
    assert result["data"] == "continued correctly"
    resumed_input = client.calls[1][-1]["content"]
    assert "[MONITOR CORRECTION]" in resumed_input
    assert "literal wildcard" in resumed_input
    assert "root task" not in resumed_input
    assert "interrupted before it became an accepted action" in resumed_input


def test_provider_cancel_closes_active_response_and_does_not_retry(monkeypatch):
    class HttpResponse:
        status_code = 200
        headers = {}

        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    response = HttpResponse()
    monkeypatch.setattr(llmcore.requests, "post", lambda *a, **k: response)
    session = llmcore.BaseSession({
        "apikey": "test", "apibase": "https://example.test", "max_retries": 3,
    })

    def parser(_response):
        yield "first chunk"
        yield "second chunk"
        return [{"type": "text", "text": "complete"}]

    stream = llmcore._stream_with_retry(
        session, "https://example.test/messages", {}, {}, parser
    )
    assert next(stream) == "first chunk"
    session.cancel_active_response()
    assert response.closed is True
    with pytest.raises(llmcore.ProviderResponseCancelled):
        next(stream)


def test_cancel_outside_provider_call_does_not_poison_next_response(monkeypatch):
    class HttpResponse:
        status_code = 200
        headers = {}
        def close(self): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False

    monkeypatch.setattr(llmcore.requests, "post", lambda *a, **k: HttpResponse())
    session = llmcore.BaseSession({"apikey": "test", "apibase": "https://example.test", "max_retries": 0})
    assert session.cancel_active_response() is False

    def parser(_response):
        yield "valid next response"
        return [{"type": "text", "text": "done"}]

    assert list(llmcore._stream_with_retry(
        session, "https://example.test/messages", {}, {}, parser
    )) == ["valid next response"]


def test_interruption_after_public_intent_prevents_announced_tool_execution():
    parent = Parent()

    class IntentClient:
        last_tools = ""

        def __init__(self):
            self.calls = 0

        def chat(self, messages, tools):
            self.calls += 1
            if False:
                yield None
            if self.calls == 1:
                parent.request("Do not execute that patch; it narrows the contract.")
                return ToolCallResponse()
            return Response()

    class IntentHandler(Handler):
        executed = False

        def do_dangerous_tool(self, args, response):
            self.executed = True
            return StepOutcome("executed", next_prompt="continue")

    handler = IntentHandler(parent)
    result = exhaust(agent_runner_loop(
        IntentClient(), "system", "root task", handler, [], max_turns=3, verbose=False
    ))

    assert result["result"] == "EXITED"
    assert handler.executed is False
