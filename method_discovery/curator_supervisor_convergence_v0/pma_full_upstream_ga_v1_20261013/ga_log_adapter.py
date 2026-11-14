"""Mechanism-owned copy of GA adapter at 9eddf569; deployed without editing GA.
Captures the same response body that GA writes to TXT, including all blocks.
"""
from public_trajectory import PublicTrajectory
from ga_log_format import prompt_body


class GATrajectory:
    def __init__(self, turn):
        self.ledger = PublicTrajectory(turn)
        self.pending = []
        self.input_count = 0
        self.finished = False
        self.started = None
        self.attempt = 0
        self.fragments = []
        self.parsed_blocks = None

    def input(self, message):
        self.input_count += 1
        self.ledger.record(f"input:{self.input_count}", "input", {
            **message, "log_prompt": prompt_body(message)})

    def begin_attempt(self, attempt):
        self.flush_partial()
        self.attempt = attempt
        self.ledger.record(f"request-attempt:{attempt}", "request_attempt", {"attempt": attempt})

    def fragment(self, text):
        self.fragments.append(text)

    def parsed_response(self, blocks):
        self.parsed_blocks = blocks

    def flush_partial(self):
        if self.fragments or self.parsed_blocks is not None:
            self.ledger.record(f"unaccepted-output:{self.attempt}", "assistant_partial", {
                "content": self.parsed_blocks if self.parsed_blocks is not None else
                           [{"type": "text", "text": text} for text in self.fragments],
                "accepted": False, "parse_finished": self.parsed_blocks is not None})
        self.fragments = []
        self.parsed_blocks = None

    def response(self, response):
        blocks = getattr(response, "public_blocks", None)
        if blocks is None:
            raise RuntimeError("public actor blocks unavailable")
        self.fragments = []
        self.parsed_blocks = None
        self.pending = [f"call:{index}" for index, _ in enumerate(response.tool_calls)]
        self.native_ids = {identity: call.id for identity, call in
                           zip(self.pending, response.tool_calls)}
        self.ledger.record("assistant", "assistant", {
            "content": blocks, "log_response": response.raw, "tool_call_ids": self.pending,
            "selected_calls": [{"tool_call_id": identity,
                "native_id": call.id or None, "name": call.function.name,
                "arguments": call.function.arguments}
                for identity, call in zip(self.pending, response.tool_calls)]})

    def start(self, call_id):
        self.started = next(identity for identity in self.pending
                            if self.native_ids[identity] == call_id)

    def result(self, call_id, outcome, content):
        call_id = next(identity for identity in self.pending
                       if self.native_ids[identity] == call_id)
        self.ledger.record("result:" + call_id, "tool_result", {
            "tool_call_id": call_id, "native_tool_call_id": self.native_ids[call_id],
            "content": content,
            "next_prompt": outcome.next_prompt, "should_exit": outcome.should_exit})
        self.pending.remove(call_id)
        self.started = None

    def settle_pending(self, status, *, started_id=None):
        if started_id is not None:
            started_id = next((identity for identity in self.pending
                              if self.native_ids[identity] == started_id), None)
        else:
            started_id = self.started
        for call_id in self.pending:
            self.ledger.record("status:" + call_id, "tool_status", {
                "tool_call_id": call_id, "native_tool_call_id": self.native_ids[call_id],
                "status": "outcome_unknown" if call_id == started_id else "not_executed",
                "reason": status})
        self.pending = []

    def finish(self, status, *, error=None, started_id=None):
        self.flush_partial()
        self.settle_pending(status, started_id=started_id)
        fields = {"status": status}
        if error is not None:
            fields.update(error_type=type(error).__name__, error_message=str(error))
        self.ledger.record("round_status", "round_status", fields)
        self.finished = True
        return self.ledger.snapshot()
