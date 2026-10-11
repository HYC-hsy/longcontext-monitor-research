"""No-model checks of the actual pilot agent_end terminal gate."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_harbor_hooks import PilotTrialHooks


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
