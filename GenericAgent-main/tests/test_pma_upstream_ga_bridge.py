"""Zero-model GA loop contract for the default-off upstream PMA bridge."""

import json
from types import SimpleNamespace

from agent_loop import BaseHandler, StepOutcome, agent_runner_loop, exhaust
from pma_upstream_bridge import UpstreamPMAClient


class FakeBridge:
    def __init__(self):
        self.calls = []

    def before_actor_call(self, attempt):
        self.calls.append(('before', attempt))
        return '<memory_context>fixture reminder</memory_context>' if attempt == 1 else None

    def actor_step(self, attempt, **fields):
        self.calls.append(('step', attempt, fields))


class FakeClient:
    last_tools = ''

    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []
        self._pending_tool_ids = []

    def chat(self, messages, tools):
        self.requests.append(([dict(message) for message in messages], tools))
        if False:
            yield None
        result = next(self.responses)
        self._pending_tool_ids = [tc.id for tc in result.tool_calls]
        return result


class Handler(BaseHandler):
    def __init__(self):
        self.parent = SimpleNamespace(task_dir=None)
        self._done_hooks = []

    def do_probe(self, args, response):
        if False:
            yield None
        return StepOutcome({'probe': 'public result'}, next_prompt='continue after probe')

    def do_no_tool(self, args, response):
        if False:
            yield None
        return StepOutcome(response, next_prompt=None)

    def turn_end_callback(self, response, tool_calls, tool_results, turn, next_prompt, exit_reason):
        return next_prompt


_UNSET = object()

def response(content, tool_calls=(), public_blocks=_UNSET):
    if public_blocks is _UNSET:
        public_blocks = [{'type': 'text', 'text': content}]
    return SimpleNamespace(content=content, tool_calls=list(tool_calls),
                           public_blocks=public_blocks, thinking='')


def test_default_off_keeps_task_loop_without_pma(monkeypatch):
    monkeypatch.delenv('GA_PMA_UPSTREAM_ENABLED', raising=False)
    client = FakeClient([response('done')])
    handler = Handler()
    outcome = exhaust(agent_runner_loop(client, 'system', 'public task', handler, [],
                                        max_turns=2, verbose=False))
    assert outcome['result'] == 'CURRENT_TASK_DONE'
    assert not hasattr(handler.parent, 'pma_upstream_bridge')
    assert client.requests[0][0][1]['content'] == 'public task'


def test_two_ga_attempts_use_one_pma_pending_reminder(monkeypatch):
    bridge = FakeBridge()
    monkeypatch.setenv('GA_PMA_UPSTREAM_ENABLED', '1')
    monkeypatch.setattr(UpstreamPMAClient, 'from_environment',
                        classmethod(lambda cls, content, turn_offset=0: bridge))
    tool = SimpleNamespace(id='tool-1', function=SimpleNamespace(
        name='probe', arguments=json.dumps({'value': 1})))
    tool2 = SimpleNamespace(id='tool-2', function=SimpleNamespace(
        name='probe', arguments=json.dumps({'value': 2})))
    visible = [
        {'type': 'text', 'text': 'before tools'},
        {'type': 'tool_use', 'id': 'tool-1', 'name': 'probe',
         'input': {'value': 1}},
        {'type': 'text', 'text': 'between tools'},
        {'type': 'tool_use', 'id': 'tool-2', 'name': 'probe',
         'input': {'value': 2}},
    ]
    client = FakeClient([response('tool choice', [tool, tool2], visible), response('done')])
    handler = Handler()
    result = exhaust(agent_runner_loop(client, 'system', 'public task', handler, [],
                                       max_turns=2, verbose=False))
    assert result['result'] == 'CURRENT_TASK_DONE'
    assert handler.parent.pma_upstream_bridge is bridge
    assert '<memory_context>fixture reminder</memory_context>' in client.requests[0][0][1]['content']
    assert 'fixture reminder' not in client.requests[1][0][0]['content']
    assert [item[0] for item in bridge.calls] == ['before', 'step', 'before', 'step']
    assert bridge.calls[1][2]['status'] == 'normal'
    assert bridge.calls[1][2]['commands'] == []
    assert bridge.calls[1][2]['public_blocks'] == visible
    results = [item for item in bridge.calls[1][2]['public_results']
               if item.get('type') == 'tool_result']
    assert [item['tool_use_id'] for item in results] == ['tool-1', 'tool-2']
    assert all('public result' in item['content'] for item in results)
    assert bridge.calls[3][2]['status'] == 'completed'


def test_unavailable_public_blocks_stops_without_silent_omission(monkeypatch):
    bridge = FakeBridge()
    monkeypatch.setenv('GA_PMA_UPSTREAM_ENABLED', '1')
    monkeypatch.setattr(UpstreamPMAClient, 'from_environment',
                        classmethod(lambda cls, content, turn_offset=0: bridge))
    tool = SimpleNamespace(id='tool-1', function=SimpleNamespace(
        name='probe', arguments=json.dumps({'value': 1})))
    client = FakeClient([response('unavailable', [tool], None)])
    try:
        exhaust(agent_runner_loop(client, 'system', 'public task', Handler(), [],
                                  max_turns=1, verbose=False))
    except RuntimeError as exc:
        assert 'cannot capture this actor response' in str(exc)
    else:
        raise AssertionError('unavailable public blocks silently accepted')
    assert [x[0] for x in bridge.calls] == ['before']


def test_incompatible_monitor_fails_before_pma_or_provider(monkeypatch):
    monkeypatch.setenv('GA_PMA_UPSTREAM_ENABLED', '1')
    monkeypatch.setenv('GA_MONITOR_ENABLED', '1')
    client = FakeClient([response('never')])
    try:
        exhaust(agent_runner_loop(client, 'system', 'public task', Handler(), [],
                                  max_turns=1, verbose=False))
    except ValueError as exc:
        assert 'cannot be combined' in str(exc)
    else:
        raise AssertionError('incompatible condition was accepted')
    assert client.requests == []


def test_visible_framework_history_reaches_pma_unchanged(monkeypatch):
    bridge = FakeBridge()
    monkeypatch.setenv('GA_PMA_UPSTREAM_ENABLED', '1')
    monkeypatch.setattr(UpstreamPMAClient, 'from_environment',
                        classmethod(lambda cls, content, turn_offset=0: bridge))
    tool = SimpleNamespace(id='tool-1', function=SimpleNamespace(
        name='probe', arguments=json.dumps({'value': 1})))
    visible = [{'type': 'text', 'text': 'visible reply'},
               {'type': 'tool_use', 'id': 'tool-1', 'name': 'probe', 'input': {'value': 1}}]
    class HistoryHandler(Handler):
        def __init__(self):
            super().__init__()
            self.history_info = ['[USER] original task']
        def turn_end_callback(self, response, tool_calls, tool_results, turn, next_prompt, exit_reason):
            return 'first line\n[WORKING MEMORY]\n[USER] original task\nCurrent turn: 1\n[FRAMEWORK] next'
    client = FakeClient([response('visible reply', [tool], visible), response('done')])
    exhaust(agent_runner_loop(client, 'system', 'public task', HistoryHandler(), [],
                              max_turns=2, verbose=False))
    projected = bridge.calls[1][2]['public_results']
    assert projected[-1]['text'] == 'first line\n[WORKING MEMORY]\n[USER] original task\nCurrent turn: 1\n[FRAMEWORK] next'
    assert client.requests[1][0][0]['content'] == projected[-1]['text']
    assert projected[0]['tool_use_id'] == 'tool-1'
    assert 'withheld' not in str(projected)


def test_next_call_reminder_is_recorded_only_after_it_exists(monkeypatch):
    class LaterBridge(FakeBridge):
        def before_actor_call(self, attempt):
            self.calls.append(('before', attempt))
            return '<memory_context>later reminder</memory_context>' if attempt == 2 else None
    bridge = LaterBridge()
    monkeypatch.setenv('GA_PMA_UPSTREAM_ENABLED', '1')
    monkeypatch.setattr(UpstreamPMAClient, 'from_environment',
                        classmethod(lambda cls, content, turn_offset=0: bridge))
    tool = SimpleNamespace(id='tool-1', function=SimpleNamespace(
        name='probe', arguments=json.dumps({'value': 1})))
    visible = [{'type': 'text', 'text': 'actor reply'},
               {'type': 'tool_use', 'id': 'tool-1', 'name': 'probe', 'input': {'value': 1}}]
    client = FakeClient([response('actor reply', [tool], visible), response('done')])
    exhaust(agent_runner_loop(client, 'system', 'public task', Handler(), [],
                              max_turns=2, verbose=False))
    first_step = bridge.calls[1][2]
    second_step = bridge.calls[3][2]
    assert 'later reminder' not in str(first_step['public_results'])
    assert 'later reminder' in str(second_step['public_input'])
    assert second_step['public_input'][0]['tool_use_id'] == 'tool-1'
    assert 'continue after probe' in second_step['public_input'][-1]['text']
