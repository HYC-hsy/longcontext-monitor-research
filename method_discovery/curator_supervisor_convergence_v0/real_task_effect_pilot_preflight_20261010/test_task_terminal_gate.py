"""No-model checks of the actual pilot agent_end terminal gate."""

import asyncio
import json
import queue
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_harbor_hooks import PilotTrialHooks


@pytest.mark.parametrize('case,expected', [
    ('done', 'CURRENT_TASK_DONE'),
    ('cap', 'MAX_TURNS_EXCEEDED'),
    ('exception', 'EXCEPTION'),
])
def test_real_task_generator_return_reaches_done_message(tmp_path, monkeypatch, case, expected):
    """Consume the real loop in GenericAgent.run, not a fabricated terminal JSON."""
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / 'GenericAgent-main'))
    import agentmain
    from agent_loop import BaseHandler, StepOutcome

    class Handler(BaseHandler):
        def __init__(self, parent, history, cwd):
            self.parent = parent
            self.history_info = history
            self.working = {}
            self._done_hooks = []
            self.code_stop_signal = []

        def do_no_tool(self, args, response):
            if False:
                yield None
            return StepOutcome(response, next_prompt=None if case == 'done' else 'continue')

        def turn_end_callback(self, response, tool_calls, tool_results, turn,
                              next_prompt, exit_reason):
            return next_prompt

    class Client:
        last_tools = ''
        log_path = ''
        backend = SimpleNamespace(extra_sys_prompt='')

        def chat(self, messages, tools):
            if False:
                yield None
            if case == 'exception':
                raise RuntimeError('offline synthetic transport failure')
            return SimpleNamespace(content='done', thinking='', stop_reason='end_turn',
                                   tool_calls=[])

    monkeypatch.setattr(agentmain, 'GenericAgentHandler', Handler)
    monkeypatch.setattr(agentmain, 'get_system_prompt', lambda: 'offline system')
    monkeypatch.setenv('GA_MAX_TURNS', '1')
    monkeypatch.delenv('GA_MONITOR_ENABLED', raising=False)
    agent = agentmain.GenericAgent.__new__(agentmain.GenericAgent)
    agent.task_queue = queue.Queue()
    agent.task_dir = str(tmp_path)
    agent.workspace_dir = str(tmp_path)
    agent.history = []
    agent.handler = None
    agent.llmclient = Client()
    agent.monitor_runtime = None
    agent.research_condition = None
    agent.research_turn_offset = 0
    agent.extra_sys_prompts = []
    agent.peer_hint = False
    agent.force_non_stream = False
    agent.verbose = False
    agent.inc_out = False
    agent.stop_sig = False
    agent.log_path = str(tmp_path / 'offline.log')
    agent.wait_monitor_correction = lambda: True
    agent.consume_resumable_interruption = lambda: []
    output = agent.put_task('Offline public task.', source='task')
    agent.task_queue.put('stop')
    agent.run()
    messages = []
    while not output.empty():
        messages.append(output.get_nowait())
    done = [item for item in messages if 'done' in item]
    assert len(done) == 1
    assert done[0]['task_terminal']['result'] == expected
    assert '[ROUND END]' not in done[0]['done']


@pytest.mark.parametrize('result,expected', [
    ('CURRENT_TASK_DONE', True), ('MAX_TURNS_EXCEEDED', False),
    ('PROVIDER_FAILURE', False), ('EXITED', False), ('EXCEPTION', False),
    (None, False), ('UNKNOWN', False),
])
@pytest.mark.parametrize('incomplete', [False, True])
@pytest.mark.parametrize('identity_case', ['valid', 'mismatch', 'missing'])
def test_actual_agent_end_requires_task_loop_terminal(tmp_path, monkeypatch,
                                                      result, expected, incomplete, identity_case):
    control, archive, monitor = (tmp_path / part for part in ('control', 'archive', 'monitor'))
    for path in (control, archive, monitor):
        path.mkdir()
    (control / 'sidecar_stopped.json').write_text(
        json.dumps({'run_id': 'run-a', 'clean': True}), encoding='utf-8')
    if incomplete:
        (monitor / 'completion_incomplete.json').write_text('{}', encoding='utf-8')

    class Environment:
        async def exec(self, command, **kwargs):
            assert command == 'cat /logs/agent/task_terminal.json'
            return SimpleNamespace(return_code=1 if identity_case == 'missing' else 0,
                                   stdout=json.dumps({
                'run_id': 'other' if identity_case == 'mismatch' else 'run-a',
                'task_id': 'task-a', 'result': result}))

        async def _run_docker_compose_command(self, command):
            assert command in (['stop', 'main'], ['start', 'main'])
            return SimpleNamespace(return_code=0)

    environment = Environment()
    trial = SimpleNamespace(agent_environment=environment, result=SimpleNamespace(
        agent_result=SimpleNamespace(metadata={
            'round_end_seen': True, 'wrapper_return_code': 0, 'archive_status': 'finished'})))
    hook = PilotTrialHooks(trial, {'control_root': str(control),
                                   'archive_root': str(archive),
                                   'run_id': 'run-a', 'task_id': 'task-a'})
    hook.container_id = 'container-a'

    async def main_id(): return 'container-a'
    hook._main_id = main_id
    monkeypatch.setattr('method_discovery.curator_supervisor_convergence_v0.'
                        'real_task_effect_pilot_preflight_20261010.pilot_harbor_hooks.subprocess.run',
                        lambda *a, **k: SimpleNamespace(returncode=0, stdout='safe process list'))

    class Capture:
        returncode = 0
        async def communicate(self): return b'', b''

    async def capture(*args, **kwargs):
        assert args[:3] == ('docker', 'cp', 'container-a:/app/.')
        kwargs['stdout'].write(b'frozen workspace')
        return Capture()

    monkeypatch.setattr('method_discovery.curator_supervisor_convergence_v0.'
                        'real_task_effect_pilot_preflight_20261010.pilot_harbor_hooks.'
                        'asyncio.create_subprocess_exec', capture)
    asyncio.run(hook.agent_end(None))
    frozen = json.loads((archive / 'agent_end_frozen.json').read_text(encoding='utf-8'))
    assert frozen['task_terminal'] == ({'run_id': 'run-a', 'task_id': 'task-a',
                                       'result': result} if identity_case == 'valid' else None)
    assert frozen['legal_agent_end'] is (expected and not incomplete and identity_case == 'valid')
    assert frozen['completion_incomplete_present'] is incomplete
