"""Zero-network checks of selected verification and single-session root routing."""

import json
import multiprocessing as mp
import threading
import time
from types import SimpleNamespace

import pytest

from monitor_agent_core.agent import MonitorAgent, verification_tools
from monitor_agent_core.process_runner import AnalysisSessions
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.runtime import MonitorRuntime
from monitor_agent_core.runtime import _verification_boundary_valid
from monitor_agent_core.verification_loop_v0 import SelectedVerification
from monitor_agent_core.workspace import MonitorWorkspace
from ga_monitor_adapter import GenericAgentMonitorAdapter
from ga import GenericAgentHandler
from agent_loop import StepOutcome, agent_runner_loop, exhaust


def workspace(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    (evidence / 'original_task.txt').write_text('Keep the route working.\n', encoding='utf-8')
    (evidence / 'public_events.jsonl').write_text(json.dumps({
        'archive_sequence': 1, 'task_turn': 1, 'boundary': 'task_control_handoff',
        'text': 'Ready for review.', 'tool_calls': [], 'tool_results': []}) + '\n', encoding='utf-8')
    task = tmp_path / 'task'
    task.mkdir()
    (task / 'route.py').write_text('print("ok")\n', encoding='utf-8')
    ws = MonitorWorkspace(evidence, tmp_path / 'private', task_mounts={'workspace': task})
    return ws, task


def selected(tmp_path):
    ws, task = workspace(tmp_path)
    due = mp.Value('q', -1)
    events = []
    check = SelectedVerification(ws, AnalysisSessions(ws.private_root, threading.Event()),
                                 lambda name, **fields: events.append((name, fields)), due)
    return check, ws, task, due, events


def definition(task, *, code=None, scope='local'):
    return {'code': code or f'exec(open({str(task / "route.py")!r}).read())',
            'type': 'python', 'timeout': 5,
            'verification': {'scope': scope, 'basis': 'Public route behavior',
                             'question': 'Does the route execute?',
                             'artifacts': ['task/workspace/route.py']}}


def test_registration_is_queued_then_real_analysis_result_is_injected(tmp_path):
    check, ws, task, due, events = selected(tmp_path)
    receipt = check.register(definition(task), 10)
    assert receipt['status'] == 'queued' and due.value == -1
    assert check.receipt is None
    check.arm_follow(10, 1)
    assert due.value == 11
    observed = check.run_due(11)
    assert observed['receipt']['result']['status'] == 'success'
    assert observed['receipt']['result']['output_excerpt'].strip() == 'ok'
    assert observed['receipt']['result']['output_path'].startswith('monitor/audit/commands/')
    assert 'Public route behavior' in check.context()
    assert 'print("ok")' not in check.context()  # output and command are distinct
    assert check.run_due(11)['status'] == 'reused'
    assert due.value == -1
    check.arm_follow(12, 1)
    assert due.value == 16  # last actual run was turn 11
    assert [name for name, _ in events].count('verification_result') == 1


def test_changed_inputs_cooldown_definition_version_and_failed_resolution(tmp_path):
    check, ws, task, due, _ = selected(tmp_path)
    first = check.register(definition(task), 1)
    check.arm_follow(1, 1)
    check.run_due(1)
    (task / 'route.py').write_text('print("changed")\n', encoding='utf-8')
    assert check.run_due(2)['status'] == 'cooldown'
    assert check.run_due(6)['receipt']['result']['output_excerpt'].strip() == 'changed'
    second = check.register(definition(task, code='raise SystemExit(3)'), 6)
    assert second['version'] == first['version'] + 1
    assert check.receipt is None
    check.run_due(7)
    with pytest.raises(ValueError, match='failed'):
        check.dispose('resolve', 'It passed')


def test_local_cannot_be_promoted_to_root_and_revision_is_explicit(tmp_path):
    check, ws, task, _, _ = selected(tmp_path)
    check.on_intervention('Check the route.')
    check.register(definition(task), 1)
    check.run_due(1)
    with pytest.raises(ValueError, match='Local verification'):
        check.dispose('resolve', 'Whole task complete', root=True)
    with pytest.raises(ValueError, match='local follow-up'):
        check.register(definition(task, scope='root'), 2)
    revised = definition(task, scope='root')
    revised['verification'].update(prior_disposition='revise', prior_reason='New root question')
    assert check.register(revised, 2)['status'] == 'queued'
    assert check.receipt is None
    check.dispose('withdraw', 'The selected check is the wrong measurement')
    assert check.current is None and not check.follow_pending


@pytest.mark.parametrize('managed', [True, False])
def test_root_uses_same_history_working_and_primary_system(tmp_path, monkeypatch, managed):
    ws, _ = workspace(tmp_path)
    config = {'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
              'max_retries': 0, 'monitor_dcec': True, 'monitor_path_control_v0': True,
              'monitor_root_scope_v1': 'off', 'monitor_verification_loop_v0': True,
              'monitor_verification_runtime_managed': managed}
    client = MonitorProviderClient('anthropic', config)
    monitor = MonitorAgent(client, ws)
    monitor.task_budget_state = lambda: (179, 180)
    ws.write_text('monitor/working.md', 'One current note.')
    client.history.append({'role': 'user', 'content': [{'type': 'text', 'text': 'Prior observation.'}]})
    handoff = {'generation': 1, 'request_id': 'completion-1', 'cursor': 1}
    monitor.completion_state = lambda: handoff
    captured = []

    def offline(tools):
        captured.append(client.assembled_request_snapshot(tools))
        if len(captured) == 1:
            return ([{'type': 'tool_use', 'id': 'correct', 'name': 'intervene',
                      'input': {'message': 'Please inspect the route.'}}], {})
        return ([{'type': 'tool_use', 'id': 'wait', 'name': 'wait',
                  'input': {'after_turns': 1}}], {})

    monkeypatch.setattr(client, '_request_once', offline)
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    action = monitor.review('Root wake', completion_pending=True, root_handoff=handoff)
    assert action.kind == 'root_intervened'
    assert client.history[0]['content'][0]['text'] == 'Prior observation.'
    assert ws.resolve_read('monitor/working.md').read_text() == 'One current note.'
    assert not (ws.private_root / 'root_working').exists()
    assert 'Prior observation.' in json.dumps(captured[0])
    assert 'One current note.' in json.dumps(captured[0])
    assert 'Task turns used: 179; limit: 180; remaining: 1.' in json.dumps(captured[0])
    assert len(captured[0]['tools']) == 7
    monitor.completion_state = lambda: None  # host has ended that handoff
    assert monitor.review('Ordinary follow').kind == 'wait'
    assert captured[1]['system'] == captured[0]['system']
    assert 'Please inspect the route.' in json.dumps(captured[1])


def test_tool_names_and_off_path_are_unchanged(tmp_path):
    assert [tool['function']['name'] for tool in verification_tools()] == [
        'file_read', 'file_write', 'file_patch', 'code_run', 'wait', 'intervene', 'allow_complete']
    ws, _ = workspace(tmp_path)
    client = MonitorProviderClient('anthropic', {
        'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
        'max_retries': 0, 'monitor_dcec': True, 'monitor_path_control_v0': True})
    monitor = MonitorAgent(client, ws)
    assert monitor.verification is None and not monitor.root_routed


def test_manual_and_managed_share_primary_contract(tmp_path):
    ws, _ = workspace(tmp_path)
    prompts = []
    modes = []
    for managed in (False, True):
        client = MonitorProviderClient('anthropic', {
            'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
            'max_retries': 0, 'monitor_dcec': True, 'monitor_path_control_v0': True,
            'monitor_verification_loop_v0': True,
            'monitor_verification_runtime_managed': managed})
        monitor = MonitorAgent(client, ws)
        prompts.append(monitor.system_prompt)
        modes.append(monitor._active_working_context())
    assert prompts[0] == prompts[1]
    assert 'manual single code_run execution' in modes[0]
    assert 'runtime-managed selected checks' in modes[1]


def verification_stub_worker(config, commands, outputs):
    outputs.put({'kind': 'ready'})
    while True:
        command = commands.get()
        if command['kind'] == 'close':
            return
        if command['kind'] == 'verification_boundary':
            time.sleep(0.06)
            config['verification_due_turn'].value = -1
            outputs.put({'kind': 'verification_boundary_release', 'ticket': command['ticket'],
                         'result': {'status': 'observed'}})


def silent_verification_worker(config, commands, outputs):
    outputs.put({'kind': 'ready'})
    while commands.get()['kind'] != 'close':
        pass


def test_task_boundary_waits_after_tool_without_correction_cancel(tmp_path):
    ws, task = workspace(tmp_path)
    cancellations = []
    runtime = MonitorRuntime(
        public_task='Keep the route working.', task_workspace=task,
        artifact_dir=tmp_path / 'runtime', task_id='offline',
        config_name='offline', interrupt_callback=cancellations.append,
        model_config={'monitor_verification_loop_v0': True,
                      'monitor_verification_runtime_managed': True},
        worker_target=verification_stub_worker)
    try:
        runtime._verification_due_turn.value = 3
        assert runtime.verification_boundary(2) is None
        started = time.monotonic()
        receipt = runtime.verification_boundary(3)
        assert time.monotonic() - started >= 0.05
        assert receipt['result']['status'] == 'observed'
        assert runtime._verification_due_turn.value == -1
        assert cancellations == []
        assert runtime.verification_boundary(4) is None
    finally:
        runtime.close()


def test_unresponsive_verification_boundary_releases_on_deadline(tmp_path):
    _, task = workspace(tmp_path)
    runtime = MonitorRuntime(
        public_task='Keep the route working.', task_workspace=task,
        artifact_dir=tmp_path / 'runtime', task_id='offline',
        config_name='offline', interrupt_callback=lambda message: None,
        model_config={'monitor_verification_loop_v0': True},
        worker_target=silent_verification_worker)
    try:
        runtime._verification_due_turn.value = 1
        runtime._run_deadline = time.monotonic() + 0.15
        receipt = runtime.verification_boundary(1)
        assert receipt['error'] == 'monitor_unavailable_or_boundary_timeout'
    finally:
        runtime.close()


def test_failed_check_output_enters_next_request_and_cannot_close(tmp_path, monkeypatch):
    ws, task = workspace(tmp_path)
    client = MonitorProviderClient('anthropic', {
        'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
        'max_retries': 0, 'monitor_dcec': True, 'monitor_path_control_v0': True,
        'monitor_verification_loop_v0': True, 'monitor_root_scope_v1': 'off'})
    monitor = MonitorAgent(client, ws)
    monitor.task_budget_state = lambda: (12, 180)
    check = monitor.verification
    check.on_intervention('Correct the route.')
    check.register(definition(task, code='print("BAD ROUTE"); raise SystemExit(2)'), 10)
    assert check.run_due(11)['receipt']['result']['status'] == 'error'
    requests = []

    def offline(tools):
        requests.append(client.assembled_request_snapshot(tools))
        return ([{'type': 'tool_use', 'id': 'patrol', 'name': 'wait',
                  'input': {'after_turns': 1, 'mode': 'patrol',
                            'result': 'resolve', 'reason': 'It passed'}}], {})

    monkeypatch.setattr(client, '_request_once', offline)
    with pytest.raises(Exception, match='exceeded'):
        monitor.review('Ordinary follow', max_turns_override=1)
    visible = json.dumps(requests[0])
    assert 'BAD ROUTE' in visible
    assert 'monitor/audit/commands/' in visible
    assert check.follow_pending


def test_root_allow_requires_root_receipt_and_defer_is_not_allow(tmp_path):
    ws, task = workspace(tmp_path)
    client = MonitorProviderClient('anthropic', {
        'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
        'max_retries': 0, 'monitor_dcec': True, 'monitor_path_control_v0': True,
        'monitor_verification_loop_v0': True, 'monitor_root_scope_v1': 'off'})
    monitor = MonitorAgent(client, ws)
    monitor.task_budget_state = lambda: (20, 180)
    handoff = {'generation': 1, 'request_id': 'completion-1', 'cursor': 1}
    monitor.completion_state = lambda: handoff
    monitor._enter_root_frame(handoff)
    monitor._refresh_completion()
    try:
        monitor.verification.register(definition(task), 20)
        monitor.verification.run_due(20)
        local = monitor.dispatch('allow_complete', {'result': 'resolve', 'reason': 'Whole task done'})
        assert local.data['status'] == 'error'
        assert 'Local verification' in local.data['error']
        revised = definition(task, scope='root')
        revised['verification'].update(prior_disposition='revise', prior_reason='Need root reach')
        monitor.verification.register(revised, 20)
        limited = monitor.dispatch('allow_complete', {'result': 'defer', 'reason': 'Verification limited'})
        assert limited.action.kind == 'incomplete_delivery'
        monitor.verification.run_due(20)
        allowed = monitor.dispatch('allow_complete', {'result': 'resolve', 'reason': 'Current root check supports this scope'})
        assert allowed.action.kind == 'allow_complete'
    finally:
        monitor._leave_root_frame()


def test_timed_out_check_does_not_immediately_reenter_or_resolve(tmp_path):
    check, ws, task, due, _ = selected(tmp_path)
    request = definition(task, code='import time; time.sleep(2)')
    request['timeout'] = 1
    check.register(request, 1)
    observed = check.run_due(1)
    assert observed['receipt']['result']['status'] == 'error'
    assert observed['receipt']['result']['reason'] == 'timeout'
    assert check.run_due(2)['status'] == 'reused'
    assert due.value == -1
    with pytest.raises(ValueError, match='failed'):
        check.dispose('resolve', 'Assume it passed')


def test_input_changed_during_check_is_not_stable_support(tmp_path):
    check, ws, task, _, _ = selected(tmp_path)
    code = f'with open({str(task / "route.py")!r}, "a") as stream: stream.write("# changed\\n")'
    check.register(definition(task, code=code), 1)
    receipt = check.run_due(1)['receipt']
    assert receipt['result']['status'] == 'success'
    assert receipt['input_changed_during_check']
    with pytest.raises(ValueError, match='changed'):
        check.dispose('resolve', 'Assume stable')
    assert check.run_due(2)['status'] == 'cooldown'
    assert check.run_due(6)['status'] == 'observed'
    request = definition(task, code='print("stable")')
    check.register(request, 6)  # a revised, non-mutating measurement
    assert check.run_due(7)['receipt']['input_changed_during_check'] is False


def test_real_task_loop_and_handler_route_through_adapter(tmp_path):
    _, task = workspace(tmp_path)
    cancellations = []
    runtime = MonitorRuntime(
        public_task='Keep the route working.', task_workspace=task,
        artifact_dir=tmp_path / 'runtime', task_id='offline', task_max_turns=2,
        config_name='offline', interrupt_callback=cancellations.append,
        model_config={'monitor_verification_loop_v0': True,
                      'monitor_verification_runtime_managed': True},
        worker_target=verification_stub_worker)
    adapter = object.__new__(GenericAgentMonitorAdapter)
    adapter.runtime = runtime
    parent = SimpleNamespace(task_dir=None, extrakeyinfo=None, intervene=None,
                             research_turn_offset=40, monitor_runtime=adapter)

    class Handler(GenericAgentHandler):
        def _in_plan_mode(self):
            return False

        def dispatch(self, *args, **kwargs):
            if False:
                yield None
            return StepOutcome('tool finished', next_prompt='continue')

    class Client:
        last_tools = ''

        def chat(self, **kwargs):
            if False:
                yield None
            return SimpleNamespace(content='Used the tool.', thinking='', stop_reason='end_turn',
                                   tool_calls=[SimpleNamespace(id='one', function=SimpleNamespace(
                                       name='file_read', arguments='{}'))])

    try:
        runtime._verification_due_turn.value = 1
        result = exhaust(agent_runner_loop(Client(), 'system', 'task', Handler(parent), [],
                                           max_turns=2, verbose=False, turn_offset=40))
        assert result['result'] == 'MAX_TURNS_EXCEEDED'
        assert runtime._task_budget_turns_used.value == 2  # not global turns 41/42
        assert runtime._task_max_turns == 2
        assert runtime._verification_due_turn.value == -1  # natural post-tool boundary ran
        assert not cancellations
        assert any(row.get('kind') == 'verification_boundary_release'
                   for row in [json.loads(line) for line in
                               (runtime.artifact_dir / 'runtime_receipts.jsonl').read_text().splitlines()])
    finally:
        runtime.close()


def delayed_boundary_worker(config, commands, outputs):
    outputs.put({'kind': 'ready'})
    while True:
        command = commands.get()
        if command['kind'] == 'close':
            return
        if command['kind'] == 'verification_boundary':
            time.sleep(0.15)  # controlled dequeue delay; host deadline is shorter
            valid = _verification_boundary_valid(config['verification_boundary_state'],
                                                 command['generation'])
            outputs.put({'kind': 'verification_boundary_release', 'ticket': command['ticket'],
                         'generation': command['generation'],
                         'result': {'status': 'observed' if valid else 'boundary_expired'}})


def test_released_host_boundary_invalidates_queued_ticket(tmp_path):
    _, task = workspace(tmp_path)
    runtime = MonitorRuntime(public_task='Keep the route working.', task_workspace=task,
        artifact_dir=tmp_path / 'runtime', task_id='offline', config_name='offline',
        interrupt_callback=lambda _: None,
        model_config={'monitor_verification_loop_v0': True},
        worker_target=delayed_boundary_worker)
    try:
        runtime._verification_due_turn.value = 1
        runtime._run_deadline = time.monotonic() + 0.05
        assert runtime.verification_boundary(1)['error'] == 'monitor_unavailable_or_boundary_timeout'
        assert runtime._verification_due_turn.value == -1
        time.sleep(0.2)
        assert runtime._verification_accepted_generation.value == 0
    finally:
        runtime.close()


def test_boundary_expiry_during_analysis_cancels_only_selected_check(tmp_path):
    check, _, task, _, events = selected(tmp_path)
    accepted = mp.Value('q', 0)
    check.accepted_generation = accepted
    check.register(definition(task, code='import time; time.sleep(2); print("late")'), 1)
    state = mp.Array('d', [1, time.monotonic() + 0.08])
    started = time.monotonic()
    result = check.run_due(1, boundary_valid=lambda: _verification_boundary_valid(state, 1),
                           boundary_generation=1)
    assert result['status'] == 'boundary_expired'
    assert time.monotonic() - started < 1.5
    assert check.receipt is None
    assert any(name == 'verification_boundary_expired' for name, _ in events)
    assert len(check.analysis.sessions) == 1
    assert check.analysis.sessions[next(iter(check.analysis.sessions))]['done'].is_set()


@pytest.mark.parametrize('managed', [False, True])
def test_defer_is_incomplete_and_invalid_root_dispositions_do_not_mutate(tmp_path, managed):
    ws, task = workspace(tmp_path)
    client = MonitorProviderClient('anthropic', {
        'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
        'max_retries': 0, 'monitor_dcec': True, 'monitor_path_control_v0': True,
        'monitor_verification_loop_v0': True, 'monitor_verification_runtime_managed': managed})
    monitor = MonitorAgent(client, ws)
    handoff = {'generation': 1, 'request_id': 'completion-1', 'cursor': 1}
    monitor.completion_state = lambda: handoff
    monitor._enter_root_frame(handoff)
    monitor._refresh_completion()
    try:
        for invalid in ('withdraw', 'revise', 'anything'):
            outcome = monitor.dispatch('allow_complete', {'result': invalid, 'reason': 'No'})
            assert outcome.data['status'] == 'error'
            assert monitor.verification is None or monitor.verification.current is None
        limited = monitor.dispatch('allow_complete', {'result': 'defer', 'reason': 'Public check unavailable'})
        assert limited.action.kind == 'incomplete_delivery'
        if managed:
            assert monitor.dispatch('allow_complete', {'result': 'resolve', 'reason': 'Assumed'}).data['status'] == 'error'
            monitor.verification.register(definition(task, scope='root'), 1)
            monitor.verification.run_due(1)
            assert monitor.dispatch('allow_complete', {
                'result': 'resolve', 'reason': 'Current root observation'}).action.kind == 'allow_complete'
    finally:
        monitor._leave_root_frame()
