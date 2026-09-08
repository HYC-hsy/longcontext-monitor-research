from types import SimpleNamespace

import json

import llmcore
from agent_loop import BaseHandler, StepOutcome, agent_runner_loop, exhaust
from experiment_conditions import BaselineCondition, condition_initial_task
from manual_completion_boundary import ManualCompletionBoundary
from research_runtime import CompletionDecision, research_context
from async_monitor_runtime import AsyncMonitorRuntime


def permanently_blocking_monitor_worker(_kwargs, requests, responses, wake_event):
    import time
    wake_event.wait()
    responses.put({"kind": "started", "request_id": "blocked-observation"})
    while True: time.sleep(10)


class SSEStreamResponse:
    status_code = 200
    headers = {}

    def __init__(self, events):
        self.events = events

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_lines(self):
        import json
        for event in self.events:
            yield ("data: " + json.dumps(event)).encode()


class Response:
    def __init__(self, content="done", tool_calls=None):
        self.content = content
        self.thinking = ""
        self.stop_reason = "end_turn"
        self.tool_calls = tool_calls or []


def test_claude_stream_emits_one_combined_usage_record():
    events = [
        {"type": "message_start", "message": {"usage": {
            "input_tokens": 120, "cache_read_input_tokens": 80,
        }}},
        {"type": "content_block_start", "content_block": {"type": "text"}},
        {"type": "content_block_delta", "delta": {
            "type": "text_delta", "text": "done",
        }},
        {"type": "content_block_stop"},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
         "usage": {"output_tokens": 17}},
        {"type": "message_stop"},
    ]
    captured = []
    with research_context({}, captured.append):
        llmcore._register_provider_call({
            "llm_call_id": "claude-call-1",
            "provider_request_event_id": "request-1",
            "call_type": "task_agent",
        })
        blocks = exhaust(llmcore._parse_claude_sse(
            [("data: " + json.dumps(event)).encode() for event in events]
        ))

    assert blocks == [{"type": "text", "text": "done"}]
    usage = [event for event in captured if event["event_type"] == "provider_usage"]
    assert len(usage) == 1
    assert usage[0]["payload"]["input_tokens"] == 120
    assert usage[0]["payload"]["output_tokens"] == 17
    assert usage[0]["payload"]["cache_read_input_tokens"] == 80


class Client:
    last_tools = ""

    def __init__(self, response):
        self.response = response

    def chat(self, messages, tools):
        if False:
            yield None
        return self.response


class RecordingClient(Client):
    def __init__(self, response):
        super().__init__(response)
        self.messages = []

    def chat(self, messages, tools):
        self.messages.append([dict(message) for message in messages])
        return super().chat(messages, tools)


class SequenceClient(RecordingClient):
    def __init__(self, responses):
        super().__init__(None)
        self.responses = iter(responses)

    def chat(self, messages, tools):
        self.messages.append([dict(message) for message in messages])
        if False: yield None
        return next(self.responses)


class Handler(BaseHandler):
    def __init__(self, decision=None):
        self.parent = SimpleNamespace(task_dir=None)
        self._done_hooks = []
        self.turn_inputs = []
        if decision is not None:
            self.completion_gate = lambda proposal: decision

    def do_no_tool(self, args, response):
        if False:
            yield None
        return StepOutcome(response, next_prompt=None)

    def turn_end_callback(self, response, tool_calls, tool_results, turn, next_prompt, exit_reason):
        self.turn_inputs.append((tool_calls, tool_results, turn, next_prompt, exit_reason))
        return next_prompt


def run_loop(handler, max_turns=2):
    return exhaust(agent_runner_loop(
        Client(Response()), "system", "task", handler, [], max_turns=max_turns, verbose=False
    ))


def test_http_200_stream_read_error_retries_before_effective_output(monkeypatch):
    responses = iter([
        SSEStreamResponse([{
            "type": "error",
            "error": {"type": "stream_read_error", "message": "stream_read_error"},
        }]),
        SSEStreamResponse([
            {"type": "response.output_text.delta", "delta": "OK"},
            {"type": "response.completed", "response": {"usage": {}}},
        ]),
    ])
    monkeypatch.setattr(llmcore.requests, "post", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(llmcore.time, "sleep", lambda _: None)
    session = SimpleNamespace(
        max_retries=1, stream=True, connect_timeout=1, read_timeout=1,
        proxies=None, verify=False, research_capture_payload=False,
    )
    events = []
    with research_context({}, events.append):
        chunks = list(llmcore._stream_with_retry(
            session, "https://example.test/v1/responses", {}, {"model": "mock"},
            lambda response: llmcore._parse_openai_sse(
                response.iter_lines(), "responses",
            ),
        ))
    assert chunks == ["OK"]
    assert sum(e["event_type"] == "provider_request_attempt" for e in events) == 2
    retry = next(e for e in events
                 if e.get("payload", {}).get("outcome") == "retryable_transport_error")
    assert retry["payload"]["error_type"] == "_RetryableStreamError"


def test_default_gate_keeps_legacy_completion_and_event_order():
    events = []
    with research_context({"run_id": "r1"}, events.append):
        result = run_loop(Handler())
    assert result["result"] == "CURRENT_TASK_DONE"
    kinds = [event["event_type"] for event in events]
    assert kinds == ["completion_proposal", "completion_decision", "termination"]


def test_monitor_completion_callback_runs_without_telemetry_or_legacy_gate():
    handler = Handler()
    seen = []

    def decide(proposal, turn, provider_link, response_content):
        seen.append((turn, response_content))
        return CompletionDecision("ALLOW_COMPLETE", ("MONITOR_ALLOWED",))

    handler.parent.completion_decision_callback = decide
    result = run_loop(handler)

    assert result["result"] == "CURRENT_TASK_DONE"
    assert seen == [(1, "done")]


def test_announced_tool_intent_is_published_before_tool_execution():
    class Runtime:
        def __init__(self): self.packets = []
        def consume_interventions(self): return []
        def archive_boundary(self, packet): self.packets.append(packet); return True

    function = SimpleNamespace(name="no_tool", arguments="{}")
    tool_call = SimpleNamespace(id="call-1", function=function)
    handler = Handler()
    runtime = Runtime()
    handler.parent.monitor_runtime = runtime
    exhaust(agent_runner_loop(
        Client(Response(content="I will run the focused check.", tool_calls=[tool_call])),
        "sys", "task", handler, [], max_turns=1, verbose=False,
    ))

    assert runtime.packets[0]["boundary"] == "post_model_pre_tool"
    assert runtime.packets[0]["tool_calls"][0]["tool_name"] == "no_tool"
    assert runtime.packets[0]["tool_results"] == []


def test_actual_task_loop_advances_while_monitor_process_is_blocked(tmp_path):
    function = SimpleNamespace(name="probe", arguments='{"path":"menu.go"}')
    first = Response(content="I will inspect the menu.", tool_calls=[
        SimpleNamespace(id="call-1", function=function),
    ])
    client = SequenceClient([first, Response(content="done")])
    handler = Handler()
    runtime = AsyncMonitorRuntime(
        {"artifact_dir": str(tmp_path)}, request_timeout=30,
        worker_target=permanently_blocking_monitor_worker,
    )
    handler.parent.monitor_runtime = runtime
    try:
        result = exhaust(agent_runner_loop(
            client, "sys", "task", handler, [], max_turns=2, verbose=False,
        ))
        assert result["result"] == "CURRENT_TASK_DONE"
        assert len(client.messages) == 2
    finally:
        runtime.close()


def test_completion_checkpoint_runs_before_gate_decision():
    order = []
    decision = CompletionDecision(decision="ALLOW_COMPLETE")
    handler = Handler(decision)
    handler.parent.completion_proposal_checkpoint_callback = (
        lambda proposal, turn, provider_link: order.append(("checkpoint", proposal.proposal_id, turn))
    )
    handler.completion_gate = lambda proposal: (
        order.append(("decision", proposal.proposal_id, proposal.turn)) or decision
    )
    exhaust(agent_runner_loop(Client(Response(content="done")), "sys", "task", handler, []))
    assert [item[0] for item in order] == ["checkpoint", "decision"]
    assert order[0][1:] == order[1][1:]


def test_continue_decision_skips_no_tool_and_runs_next_turn():
    decision = CompletionDecision(decision="CONTINUE", reason_codes=("TEST",), next_prompt="continue")
    events = []
    with research_context({}, events.append):
        result = run_loop(Handler(decision), max_turns=2)
    assert result["result"] == "MAX_TURNS_EXCEEDED"
    assert [e["event_type"] for e in events].count("completion_proposal") == 2


def test_manual_continue_message_is_delivered_to_the_next_turn(tmp_path):
    handler = Handler()
    boundary = ManualCompletionBoundary(tmp_path, timeout_seconds=1, poll_seconds=0.001)
    seen_proposals = 0

    def decide(proposal, turn, provider_link):
        nonlocal seen_proposals
        seen_proposals += 1
        if seen_proposals == 1:
            (tmp_path / f"decision_{proposal.proposal_id}.json").write_text(
                '{"decision":"CONTINUE","message":"Inspect the timer contract again."}',
                encoding="utf-8",
            )
            return boundary(proposal, turn, provider_link)
        return CompletionDecision(decision="ALLOW_COMPLETE")

    handler.parent.completion_decision_callback = decide
    with research_context({}, lambda event: None):
        result = run_loop(handler, max_turns=2)

    assert result["result"] == "CURRENT_TASK_DONE"
    assert len(handler.turn_inputs) == 2
    assert handler.turn_inputs[0][3] == "Inspect the timer contract again."
    assert handler.turn_inputs[0][4] == {}


def test_abstain_is_distinct_exit():
    decision = CompletionDecision(decision="ABSTAIN", reason_codes=("NO_AUTHORITY",))
    result = run_loop(Handler(decision))
    assert result["result"] == "EXITED"


def test_provider_error_is_not_a_completion_proposal():
    class ErrorAwareHandler(Handler):
        def do_no_tool(self, args, response):
            if False:
                yield None
            if response.content.startswith("!!!Error:"):
                return StepOutcome({}, next_prompt="retry provider call")
            return StepOutcome(response, next_prompt=None)

    events = []
    handler = ErrorAwareHandler()
    with research_context({}, events.append):
        result = exhaust(agent_runner_loop(
            Client(Response(content="!!!Error: ReadTimeout: timed out")),
            "system", "task", handler, [], max_turns=1, verbose=False,
        ))
    assert result["result"] == "PROVIDER_FAILURE"
    assert events[-1]["payload"]["result"] == "PROVIDER_FAILURE"
    assert not [event for event in events if event["event_type"] == "completion_proposal"]


def test_resume_turn_offset_uses_global_turns_without_reducing_local_budget():
    decision = CompletionDecision(decision="CONTINUE", next_prompt="continue")
    events = []
    handler = Handler(decision)
    with research_context({}, events.append):
        result = exhaust(agent_runner_loop(
            Client(Response()), "system", "task", handler, [], max_turns=2,
            verbose=False, turn_offset=56,
        ))
    assert result["result"] == "MAX_TURNS_EXCEEDED"
    assert [item[2] for item in handler.turn_inputs] == [57, 58]
    proposals = [event for event in events if event["event_type"] == "completion_proposal"]
    assert [event["payload"]["turn"] for event in proposals] == [57, 58]
    assert events[-1]["internal_turn"] == 58


def test_handler_uses_opt_in_evidence_kernel_without_legacy_ledger():
    decision = CompletionDecision(decision="VERIFY", reason_codes=("MISSING",), next_prompt="verify")
    parent = SimpleNamespace(
        task_dir=None, obligation_ledger=None,
        evidence_completion_kernel=lambda proposal: decision,
    )
    from ga import GenericAgentHandler
    handler = GenericAgentHandler(parent)
    assert handler.completion_gate(SimpleNamespace(turn=1)).decision == "VERIFY"


def test_telemetry_is_semantically_transparent_for_default_gate():
    plain = Handler()
    observed = Handler()
    plain_result = run_loop(plain)
    events = []
    with research_context({"run_id": "observed"}, events.append):
        observed_result = run_loop(observed)
    assert plain_result["result"] == observed_result["result"]
    assert plain_result["data"].content == observed_result["data"].content
    p_tools, p_results, p_turn, p_prompt, p_exit = plain.turn_inputs[0]
    o_tools, o_results, o_turn, o_prompt, o_exit = observed.turn_inputs[0]
    assert (p_tools, p_results, p_turn, p_prompt) == (o_tools, o_results, o_turn, o_prompt)
    assert p_exit["result"] == o_exit["result"]
    assert p_exit["data"].content == o_exit["data"].content
    assert p_tools == [{"tool_name": "no_tool", "args": {"_index": 0, "_tool_num": 1}}]
    assert events


def test_intervention_provider_and_action_are_explicitly_linked(monkeypatch):
    class HttpResponse:
        status_code = 200
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *args): return False

    monkeypatch.setattr(llmcore.requests, "post", lambda *args, **kwargs: HttpResponse())

    class ProviderClient(Client):
        def chat(self, messages, tools):
            session = SimpleNamespace(
                max_retries=0, stream=False, connect_timeout=1, read_timeout=1,
                proxies=None, verify=False, research_capture_payload=False,
            )
            def parser(_response):
                if False: yield None
                return [{"type": "text", "text": "done"}]
            yield from llmcore._stream_with_retry(
                session, "https://example.test/v1/messages", {},
                {"model": "mock", "messages": messages}, parser,
            )
            return self.response

    events = []
    with research_context({"run_id": "linked"}, events.append):
        handler = Handler()
        handler.parent.research_condition = BaselineCondition.static_checklist(["Deliver URL"])
        exhaust(agent_runner_loop(
            ProviderClient(Response()), "system", "task", handler, [], max_turns=1, verbose=False
        ))
    by_kind = {event["event_type"]: event for event in events}
    intervention = by_kind["intervention"]
    request = by_kind["provider_request_ready"]
    action = by_kind["action_selected"]
    occurrence = intervention["payload"]["injection_occurrence_id"]
    assert request["payload"]["intervention_event_id"] == intervention["event_id"]
    assert request["payload"]["injection_occurrence_id"] == occurrence
    assert action["payload"]["intervention_event_id"] == intervention["event_id"]
    assert action["payload"]["injection_occurrence_id"] == occurrence
    assert action["payload"]["provider_request_event_id"] == request["event_id"]
    assert action["llm_call_id"] == request["llm_call_id"]
    assert action["parent_event_id"] == request["event_id"]
