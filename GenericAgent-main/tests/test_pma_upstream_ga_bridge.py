"""Zero-model GA loop contract for the default-off upstream PMA bridge."""

import json
from types import SimpleNamespace

from agent_loop import BaseHandler, StepOutcome, agent_runner_loop, exhaust
from pma_upstream_bridge import UpstreamPMAClient


def test_uncapped_pending_event_fails_when_host_worker_exits(tmp_path):
    requests, responses = tmp_path / 'requests', tmp_path / 'responses'
    requests.mkdir()
    responses.mkdir()
    (responses / 'worker_exit.json').write_text(json.dumps(
        {'run_id': 'r', 'worker_return_code': 1}), encoding='utf-8')
    client = UpstreamPMAClient(run_id='r', task_id='t', requests=requests,
                               responses=responses, deadline='uncapped')
    try:
        client.exchange('task_start', initial_user_content='public task')
    except RuntimeError as error:
        assert 'worker exited without receipt' in str(error)
    else:
        raise AssertionError('dead worker left an uncapped client waiting')
    assert len(list(requests.glob('*.json'))) == 1


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

    def chat(self, messages, tools):
        self.requests.append(([dict(message) for message in messages], tools))
        if False:
            yield None
        return next(self.responses)


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


def response(content, tool_calls=()):
    return SimpleNamespace(content=content, tool_calls=list(tool_calls), thinking='')


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
    client = FakeClient([response('tool choice', [tool]), response('done')])
    handler = Handler()
    result = exhaust(agent_runner_loop(client, 'system', 'public task', handler, [],
                                       max_turns=2, verbose=False))
    assert result['result'] == 'CURRENT_TASK_DONE'
    assert handler.parent.pma_upstream_bridge is bridge
    assert '<memory_context>fixture reminder</memory_context>' in client.requests[0][0][1]['content']
    assert 'fixture reminder' not in client.requests[1][0][0]['content']
    assert [item[0] for item in bridge.calls] == ['before', 'step', 'before', 'step']
    assert bridge.calls[1][2]['status'] == 'normal'
    assert bridge.calls[1][2]['commands'][0].find('probe') >= 0
    assert bridge.calls[3][2]['status'] == 'completed'


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
