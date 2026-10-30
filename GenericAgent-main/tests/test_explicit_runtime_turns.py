"""Explicit runner turns survive plan-mode for shared GA/PMA task loop."""
import os
from types import SimpleNamespace
from unittest.mock import patch
import pytest

from agent_loop import agent_runner_loop, exhaust
from test_task_interruption import Parent, Handler


@pytest.mark.parametrize('flags', [
    {}, {'GA_PMA_UPSTREAM_ENABLED': '1'}])
@pytest.mark.parametrize('turns,expected', [('uncapped', 3), ('2', 2)])
def test_explicit_turns_ignore_plan_mode(flags, turns, expected):
    handler = Handler(Parent())
    class Client:
        last_tools = ''
        calls = 0
        def chat(self, messages, tools):
            self.calls += 1
            handler.max_turns = 1
            pending = self.calls < 3
            response = SimpleNamespace(content='continue' if pending else 'done',
                thinking='', stop_reason='end_turn', tool_calls=(
                    [SimpleNamespace(id=str(self.calls), function=SimpleNamespace(
                        name='bad_json', arguments='{"msg":"retry"}'))] if pending else []))
            if False:
                yield None
            return response
    client = Client()
    env = dict(flags, GA_EXPERIMENT_RUNTIME_POLICY='v1', GA_EXPERIMENT_TASK_TURNS=turns)
    # Bridge behavior has its own tests; this checks the real task loop limit.
    with patch.dict(os.environ, env, clear=True), patch(
            'pma_upstream_bridge.UpstreamPMAClient.from_environment', return_value=None):
        exhaust(agent_runner_loop(client, 'system', 'task', handler, [],
            max_turns=None if turns == 'uncapped' else int(turns), verbose=False))
    assert client.calls == expected


def test_complete_response_phase_budget_is_owned_by_harbor():
    import llmcore
    with patch.dict(os.environ, {'GA_EXPERIMENT_RUNTIME_POLICY': 'v1',
                                'GA_TASK_DEADLINE_EPOCH': 'uncapped'}, clear=True):
        assert llmcore._task_deadline(SimpleNamespace()) is None
