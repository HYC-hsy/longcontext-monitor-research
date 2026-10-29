"""The explicit A/U turn policy survives mutable plan-mode limits."""
import os
from types import SimpleNamespace
from unittest.mock import patch

from agent_loop import agent_runner_loop, exhaust
from test_task_interruption import Parent, Handler


class Client:
    last_tools = ''

    def __init__(self, handler):
        self.handler = handler
        self.calls = 0

    def chat(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            # enter_plan_mode may lower the mutable handler limit mid-run.
            self.handler.max_turns = 1
        pending = self.calls < 3
        response = SimpleNamespace(content='continue' if pending else 'done',
            thinking='', stop_reason='end_turn',
            tool_calls=([SimpleNamespace(id=str(self.calls),
                function=SimpleNamespace(name='bad_json', arguments='{"msg":"retry"}'))]
                if pending else []))
        if False:
            yield None
        return response


def test_explicit_ga_only_uncapped_turns_ignore_plan_mode_limit():
    parent = Parent()
    handler = Handler(parent)
    client = Client(handler)
    # The native A/U adapter leaves disabled feature flags absent.
    env = {'GA_EXPERIMENT_GA_ONLY_POLICY': 'A/U',
           'GA_EXPERIMENT_TASK_TURNS': 'uncapped'}
    with patch.dict(os.environ, env, clear=True):
        result = exhaust(agent_runner_loop(client, 'system', 'task', handler, [],
            max_turns=None, verbose=False))
    assert result['result'] == 'EXITED'
    assert client.calls == 3


def test_ga_only_without_explicit_policy_keeps_legacy_limit():
    parent = Parent()
    handler = Handler(parent)
    client = Client(handler)
    with patch.dict(os.environ, {'GA_EXPERIMENT_TASK_TURNS': 'uncapped',
                                 'GA_PMA_UPSTREAM_ENABLED': '0'}, clear=True):
        exhaust(agent_runner_loop(client, 'system', 'task', handler, [],
            max_turns=3, verbose=False))
    assert client.calls == 1


def test_other_binding_cannot_activate_ga_only_turn_policy():
    parent = Parent()
    handler = Handler(parent)
    client = Client(handler)
    env = {'GA_EXPERIMENT_GA_ONLY_POLICY': 'B/U',
           'GA_EXPERIMENT_TASK_TURNS': 'uncapped',
           'GA_PMA_UPSTREAM_ENABLED': '0'}
    with patch.dict(os.environ, env, clear=True):
        exhaust(agent_runner_loop(client, 'system', 'task', handler, [],
            max_turns=3, verbose=False))
    assert client.calls == 1
