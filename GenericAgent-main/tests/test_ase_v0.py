"""Zero-network tests of ASE-v0 representation and unchanged seven-tool control loop."""

import hashlib
import json
import multiprocessing as mp
import queue
import threading
import time
from types import SimpleNamespace

import pytest

from monitor_agent_core.agent import MONITOR_TOOLS, MonitorAgent
from monitor_agent_core.ase_v0 import ASE_REFERENCE_MAX_CHARS, reference_surface
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.root_scope_v1 import ROOT_SYSTEM_PROMPT
from monitor_agent_core.runtime import ASE_CONTROL_ACTIONS, ASEFeedbackBarrier, MonitorRuntime
from monitor_agent_core.workspace import MonitorWorkspace


def make_monitor(tmp_path, *, ase=True, cqs=False, meta=None, live=None):
    evidence = tmp_path / 'evidence'
    evidence.mkdir(parents=True)
    (evidence / 'original_task.txt').write_text('Maintain the public route.', encoding='utf-8')
    (evidence / 'public_events.jsonl').write_text('', encoding='utf-8')
    task = tmp_path / 'task'
    task.mkdir()
    (task / 'router.py').write_text('ROUTE = True\n', encoding='utf-8')
    workspace = MonitorWorkspace(evidence, tmp_path / 'private', task_mounts={'workspace': task})
    workspace.write_text('monitor/working.md', 'LOCAL_WORKING_SENTINEL')
    config = {'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
              'max_retries': 0, 'monitor_adaptive_supervisory_environment': ase}
    if meta is not None:
        config['monitor_ase_meta_regulation'] = meta
    if live is not None:
        config['monitor_live_intervention'] = live
    if not ase:
        config.update({'monitor_dcec': True, 'monitor_path_control_v0': True,
                       'monitor_verification_loop_v0': True,
                       'monitor_verification_runtime_managed': False,
                       'monitor_coarse_to_fine_surface': True,
                       'monitor_decision_conditioned_measurement': True,
                       'monitor_control_question_state': cqs})
    elif cqs:
        config['monitor_control_question_state'] = True
    client = MonitorProviderClient('anthropic', config)
    monitor = MonitorAgent(client, workspace)
    monitor.task_budget_state = lambda: (12, 300)
    return monitor, client, workspace


def scripted(client, monkeypatch, calls):
    snapshots = []

    def offline_once(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        rationale, name, args = calls[len(snapshots) - 1]
        blocks = ([{'type': 'text', 'text': rationale}] if rationale else [])
        blocks.append({'type': 'tool_use', 'id': f'call-{len(snapshots)}',
                       'name': name, 'input': args})
        return blocks, {}

    monkeypatch.setattr(client, '_request_once', offline_once)
    return snapshots


def visible(snapshot):
    return json.dumps(snapshot['messages'], ensure_ascii=False)


def rows(workspace):
    path = workspace.private_root / 'audit/dialogue.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def root(monitor):
    handoff = {'generation': 1, 'request_id': 'completion-1', 'cursor': 1}
    (monitor.workspace.evidence_root / 'public_events.jsonl').write_text(
        json.dumps({'archive_sequence': 1, 'task_turn': 12, 'boundary': 'completion',
                    'text': 'Ready for review.', 'tool_calls': [], 'tool_results': []}) + '\n',
        encoding='utf-8')
    monitor.completion_state = lambda: handoff
    return handoff


def test_reference_full_exposure_and_model_owned_revision(tmp_path):
    monitor, _, ws = make_monitor(tmp_path)
    absent, meta = reference_surface(ws)
    assert meta['status'] == 'absent' and meta['source_characters'] == 0
    assert 'no task interpretation was generated' in absent
    source = 'START_' + 'm' * 2750 + 'MIDDLE_MISSION_SENTINEL' + 'm' * 2750 + '_END'
    written = monitor.dispatch('file_write', {'path': 'monitor/reference.md', 'content': source})
    assert written.data['sha256'] == hashlib.sha256(source.encode()).hexdigest()
    surface, meta = reference_surface(ws)
    assert source in surface and 'MIDDLE_MISSION_SENTINEL' in surface
    assert not meta['truncated']
    assert meta['source_characters'] == len(source)
    assert meta['visible_characters'] == len(source)
    assert meta['source_sha256'] == hashlib.sha256(source.encode()).hexdigest()
    monitor.dispatch('file_patch', {'path': 'monitor/reference.md',
                                    'old_text': 'START_', 'new_text': 'REVISED_'})
    revised, _ = reference_surface(ws)
    assert 'REVISED_' in revised
    assert len([r for r in rows(ws) if r['event'] == 'curator_task_book_mutated']) == 2


def test_reference_source_limit_atomic_write_patch_and_initialization(tmp_path):
    monitor, _, ws = make_monitor(tmp_path)
    maximum = ASE_REFERENCE_MAX_CHARS
    before = 'A' * (maximum - 2) + 'Q'
    assert monitor.dispatch('file_write', {'path': 'monitor/reference.md', 'content': before}).data['characters'] == maximum - 1
    assert monitor.dispatch('file_patch', {'path': 'monitor/reference.md',
                                          'old_text': 'Q', 'new_text': 'BBB'}).data['status'] == 'error'
    assert monitor.dispatch('file_write', {'path': 'monitor//reference.md',
                                          'content': 'X' * (maximum + 1)}).data['status'] == 'error'
    assert ws.resolve_read('monitor/reference.md').read_bytes() == before.encode()
    assert reference_surface(ws)[1]['truncated'] is False
    assert monitor.dispatch('file_write', {'path': 'monitor/reference.md',
                                          'content': 'Z' * maximum}).data['characters'] == maximum
    assert monitor._ase_reference_ready()
    ws.write_text('monitor/reference.md', 'Z' * (maximum + 1))  # Simulate pre-existing external state.
    surface, metadata = reference_surface(ws)
    assert metadata['status'] == 'oversized' and 'Reference oversized' in surface
    assert not monitor._ase_reference_ready()
    assert [r for r in rows(ws) if r['event'] == 'ase_reference_mutation_failed']


def test_ase_feedback_barrier_requires_new_model_event_and_cursor():
    audit = []
    barrier = ASEFeedbackBarrier(lambda event, **fields: audit.append((event, fields)))
    barrier.start(task_turn=76, cursor=101, action_locator='dialogue#9', submission_id='sent-1')
    assert not barrier.permits(task_turn=76, cursor=102,
                               model_feedback_turn=76, model_feedback_cursor=102)
    assert not barrier.permits(task_turn=77, cursor=103,
                               model_feedback_turn=76, model_feedback_cursor=102)
    assert not barrier.permits(task_turn=77, cursor=101,
                               model_feedback_turn=77, model_feedback_cursor=103)
    assert barrier.permits(task_turn=77, cursor=103,
                            model_feedback_turn=77, model_feedback_cursor=103)
    assert barrier.permits(task_turn=77, cursor=103,
                            model_feedback_turn=77, model_feedback_cursor=103)
    assert [event for event, _ in audit] == [
        'ase_feedback_barrier_started', 'ase_feedback_barrier_blocked_wake',
        'ase_feedback_barrier_blocked_wake', 'ase_feedback_barrier_blocked_wake',
        'ase_feedback_barrier_satisfied']


def test_archived_model_feedback_not_same_turn_tool_delta(tmp_path):
    runtime = MonitorRuntime.__new__(MonitorRuntime)
    runtime._archive_lock = threading.Lock()
    runtime._sequence = 0
    runtime._eis_enabled = False
    runtime.events_path = tmp_path / 'public_events.jsonl'
    runtime.synopsis_path = tmp_path / 'synopsis.jsonl'
    runtime._latest_public_cursor = mp.Value('q', 0)
    runtime._latest_model_feedback = mp.Array('q', [0, 0])
    runtime._latest_task_turn = mp.Value('q', 0)
    barrier = ASEFeedbackBarrier(lambda *_args, **_fields: None)
    assert runtime._archive({'boundary': 'post_model_pre_tool', 'task_turn': 76}) == 1
    barrier.start(task_turn=76, cursor=1, submission_id='sent-1')
    assert runtime._archive({'boundary': 'post_tool_pre_next_llm', 'task_turn': 76}) == 2
    assert list(runtime._latest_model_feedback[:]) == [76, 1]
    assert not barrier.permits(task_turn=76, cursor=2,
                               model_feedback_turn=76, model_feedback_cursor=1)
    assert runtime._archive({'boundary': 'post_model_pre_tool', 'task_turn': 77}) == 3
    # The queued old boundary cannot use an event newer than its own cursor.
    assert not barrier.permits(task_turn=76, cursor=2,
                               model_feedback_turn=77, model_feedback_cursor=3)
    assert barrier.permits(task_turn=77, cursor=3,
                            model_feedback_turn=77, model_feedback_cursor=3)
    assert runtime._archive({'boundary': 'task_control_handoff', 'task_turn': 78}) == 4
    barrier.start(task_turn=77, cursor=3, submission_id='root-sent')
    assert not barrier.permits(task_turn=77, cursor=4,
                               model_feedback_turn=77, model_feedback_cursor=4)
    assert barrier.permits(task_turn=78, cursor=4,
                            model_feedback_turn=78, model_feedback_cursor=4)


@pytest.mark.skip(reason='Replaced by delivery-acknowledged worker tests in test_curator_supervisor_v0.py')
def test_ase_worker_blocks_queued_same_turn_wake_then_reviews_new_feedback(tmp_path, monkeypatch):
    import monitor_agent_core.agent as agent_module
    import monitor_agent_core.provider as provider_module
    from monitor_agent_core.runtime import _worker

    reviewed, audited = [], []

    class FakeClient:
        def __init__(self, *_args):
            self.captured_root_handoffs = set()

    class FakeMonitor:
        ase_v0 = True
        dcec_enabled = False
        root_routed = False
        verification = None
        max_review_turns = 20

        def __init__(self, *_args, **_kwargs):
            self.cqs = SimpleNamespace(last_call={'locator': 'dialogue#intervene'})

        def _progress(self, event, **fields):
            audited.append((event, fields))

        def review(self, context, **_kwargs):
            reviewed.append(context)
            if len(reviewed) == 2:
                self.intervention_callback('Correct the public route.')
                return SimpleNamespace(kind='local_intervened', payload={})
            return SimpleNamespace(kind='wait', payload={'after_turns': 1, 'mode': 'patrol'})

    monkeypatch.setattr(provider_module, 'MonitorProviderClient', FakeClient)
    monkeypatch.setattr(agent_module, 'MonitorAgent', FakeMonitor)
    evidence, task = tmp_path / 'evidence', tmp_path / 'task'
    evidence.mkdir()
    task.mkdir()
    commands, outputs = queue.Queue(), queue.Queue()
    config = {'config_name': 'offline', 'model_config': {}, 'task_id': 'fixture',
              'evidence_root': str(evidence), 'private_root': str(tmp_path / 'private'),
              'task_workspace': str(task), 'max_review_turns': 20,
              'stop_event': threading.Event(), 'active_completion': mp.Value('q', 0),
              'completion_cursor': mp.Value('q', 0), 'latest_task_turn': mp.Value('q', 0),
              'latest_public_cursor': mp.Value('q', 0),
              'latest_model_feedback': mp.Array('q', [0, 0])}
    worker = threading.Thread(target=_worker, args=(config, commands, outputs), daemon=True)
    worker.start()
    try:
        assert outputs.get(timeout=3)['kind'] == 'ready'
        config['latest_task_turn'].value = 76
        config['latest_public_cursor'].value = 1
        with config['latest_model_feedback'].get_lock():
            config['latest_model_feedback'][0] = 76
            config['latest_model_feedback'][1] = 1
        commands.put({'kind': 'boundary', 'cursor': 1, 'task_turn': 76})
        assert outputs.get(timeout=3)['kind'] == 'intervention'
        commands.put({'kind': 'boundary', 'cursor': 2, 'task_turn': 76})
        # An old queued same-turn wake is discarded by the turn schedule.
        time.sleep(.05)
        assert len(reviewed) == 2
        # A later boundary with no newer model response is rejected by the barrier.
        commands.put({'kind': 'boundary', 'cursor': 2, 'task_turn': 77})
        deadline = time.monotonic() + 3
        while not any(event == 'ase_feedback_barrier_blocked_wake' for event, _ in audited):
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert len(reviewed) == 2
        with config['latest_model_feedback'].get_lock():
            config['latest_model_feedback'][0] = 77
            config['latest_model_feedback'][1] = 3
        commands.put({'kind': 'boundary', 'cursor': 3, 'task_turn': 77})
        assert outputs.get(timeout=3)['kind'] == 'review_silent'
        assert len(reviewed) == 3
        assert sum(event == 'ase_feedback_barrier_satisfied' for event, _ in audited) == 1
        assert sum(event == 'ase_feedback_barrier_started' for event, _ in audited) == 1
    finally:
        commands.put({'kind': 'close'})
        worker.join(timeout=3)


@pytest.mark.skip(reason='Replaced by delivery-acknowledged worker tests in test_curator_supervisor_v0.py')
def test_delivery_failure_is_recorded_without_same_turn_recontrol_or_double_send(tmp_path, monkeypatch):
    import monitor_agent_core.agent as agent_module
    import monitor_agent_core.provider as provider_module
    from monitor_agent_core.runtime import _worker

    reviewed, audited, delivery_attempts = [], [], []

    class ThreadProcess:
        def __init__(self, *, target, args, daemon):
            self.thread = threading.Thread(target=target, args=args, daemon=daemon)

        def start(self):
            self.thread.start()

        def is_alive(self):
            return self.thread.is_alive()

        def join(self, timeout=None):
            self.thread.join(timeout)

        def terminate(self):
            raise AssertionError('The fixture worker must close normally')

    class FakeClient:
        def __init__(self, *_args):
            self.captured_root_handoffs = set()

    class FakeMonitor:
        ase_v0 = True
        dcec_enabled = False
        root_routed = False
        verification = None
        max_review_turns = 20

        def __init__(self, *_args, **_kwargs):
            self.cqs = SimpleNamespace(last_call={'locator': 'dialogue#intervene'})

        def _progress(self, event, **fields):
            audited.append((event, fields))

        def review(self, _context, **_kwargs):
            reviewed.append(len(reviewed) + 1)
            if len(reviewed) == 2:
                self.intervention_callback('Inspect the public route.')
                return SimpleNamespace(kind='local_intervened', payload={})
            return SimpleNamespace(kind='wait', payload={'after_turns': 1, 'mode': 'patrol'})

    monkeypatch.setattr(provider_module, 'MonitorProviderClient', FakeClient)
    monkeypatch.setattr(agent_module, 'MonitorAgent', FakeMonitor)
    task = tmp_path / 'task'
    task.mkdir()

    def failed_delivery(message):
        delivery_attempts.append(message)
        raise RuntimeError('fixture delivery failure')

    runtime = MonitorRuntime(public_task='Public route.', task_workspace=task,
                             artifact_dir=tmp_path / 'artifacts', config_name='offline',
                             model_config={'monitor_adaptive_supervisory_environment': True},
                             interrupt_callback=failed_delivery, task_id='fixture:ase',
                             worker_target=_worker, process_factory=ThreadProcess)
    try:
        receipts = runtime.artifact_dir / 'runtime_receipts.jsonl'
        deadline = time.monotonic() + 3
        while not (receipts.exists() and '"kind": "ready"' in receipts.read_text(encoding='utf-8')):
            assert time.monotonic() < deadline
            time.sleep(.01)
        runtime.archive_boundary({'boundary': 'post_model_pre_tool', 'task_turn': 76,
                                  'text': 'Task model response.'})
        deadline = time.monotonic() + 3
        while True:
            records = [json.loads(line) for line in receipts.read_text(encoding='utf-8').splitlines()] \
                if receipts.exists() else []
            if any(row.get('kind') == 'intervention' and row.get('delivery') == 'failed'
                   for row in records):
                break
            assert time.monotonic() < deadline
            time.sleep(.01)
        runtime.archive_boundary({'boundary': 'post_tool_pre_next_llm', 'task_turn': 76,
                                  'text': 'Same-turn tool return.'})
        time.sleep(.05)
        assert len(reviewed) == 2 and delivery_attempts == ['Inspect the public route.']
        runtime.archive_boundary({'boundary': 'post_model_pre_tool', 'task_turn': 77,
                                  'text': 'New Task model feedback.'})
        deadline = time.monotonic() + 3
        while len(reviewed) < 3:
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert len(reviewed) == 3 and len(delivery_attempts) == 1
        assert [event for event, _ in audited].count('ase_feedback_barrier_satisfied') == 1
    finally:
        runtime.close()


def test_turn_zero_and_provider_ready_composition_no_working_ledger(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    reference = 'REFERENCE_SENTINEL:' + 'a' * 2750 + 'MIDDLE_MISSION_SENTINEL' + 'b' * 2750
    sends = scripted(client, monkeypatch, [
        ('', 'file_read', {'path': 'task/original_task.txt'}),
        ('', 'file_read', {'path': 'task/workspace/router.py'}),
        ('', 'file_write', {'path': 'monitor/reference.md',
                            'content': reference}),
        ('Watch route use.', 'wait', {'mode': 'follow', 'after_turns': 2}),
    ])
    assert monitor.review('Initialization').kind == 'wait'
    assert len(sends) == 4
    assert [tool['function']['name'] for tool in sends[0]['tools']] == [
        'file_read', 'file_write', 'file_patch', 'code_run', 'wait', 'intervene', 'allow_complete']
    assert [tool['function']['parameters'] for tool in sends[0]['tools']] == [
        tool['function']['parameters'] for tool in MONITOR_TOOLS]
    assert 'self-authored text' in sends[0]['tools'][3]['function']['description']
    assert 'verification' not in json.dumps(sends[0]['tools'])
    assert 'result' not in sends[0]['tools'][-1]['function']['parameters']['properties']
    assert 'monitor/reference.md' in sends[0]['system']
    assert 'task/original_task.txt' in sends[0]['system']
    assert 'Reference absent' in visible(sends[0])
    assert 'LOCAL_WORKING_SENTINEL' not in visible(sends[0])
    assert 'REFERENCE_SENTINEL' in visible(sends[3])
    assert reference in visible(sends[3])
    assert 'Supervisory Situation' in visible(sends[0])
    assert 'Situation unchanged through cursor 0' in visible(sends[3])
    assert visible(sends[3]).index('REFERENCE_SENTINEL') < visible(sends[3]).index('Situation unchanged')
    injections = [r for r in rows(ws) if r['event'] == 'ase_context_injected']
    assert len(injections) == 4
    assert injections[-1]['reference_source_characters'] > 0
    assert injections[-1]['reference_visible_characters'] == len(reference)
    assert injections[-1]['reference_truncated'] is False
    assert injections[-1]['composition_order'] == ['task_book', 'situation']
    assert monitor.dispatch('file_read', {'path': 'monitor/working.md'}).data['content'] == 'LOCAL_WORKING_SENTINEL'


def test_initialization_requires_model_authored_reference_before_wait(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    sends = scripted(client, monkeypatch, [
        ('', 'wait', {'after_turns': 3, 'mode': 'patrol'}),
        ('', 'file_write', {'path': 'monitor/reference.md', 'content': '   '}),
        ('', 'wait', {'after_turns': 3, 'mode': 'follow'}),
        ('', 'file_write', {'path': 'monitor/reference.md',
                            'content': 'Public route response matters.'}),
        ('', 'wait', {'after_turns': 3, 'mode': 'patrol'}),
    ])
    action = monitor.review('Initialization')
    assert action.kind == 'wait' and action.payload['mode'] == 'patrol'
    assert len(sends) == 5
    feedback = [r['data'] for r in rows(ws) if r['event'] == 'tool_result'
                and isinstance(r.get('data'), dict)
                and r['data'].get('status') == 'reference_initialization_pending']
    assert len(feedback) == 2
    assert all('route' not in str(item).lower() for item in feedback)
    assert [r['event'] for r in rows(ws) if r['event'].startswith('ase_reference_initialization_')] == [
        'ase_reference_initialization_pending', 'ase_reference_initialization_pending',
        'ase_reference_initialization_ready']
    assert ws.resolve_read('monitor/reference.md').read_text(encoding='utf-8') == 'Public route response matters.'
    assert not [r for r in rows(ws) if r['event'] == 'ase_reconsideration_boundary']


@pytest.mark.skip(reason='Queued intervention no longer creates model-visible active control')
def test_inactive_patrol_is_one_turn_but_active_patrol_reconsiders(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Public route response matters.')
    sends = scripted(client, monkeypatch, [('', 'wait', {'after_turns': 1, 'mode': 'patrol'})])
    assert monitor.review('Initial').payload['mode'] == 'patrol'
    assert len(sends) == 1
    assert not [r for r in rows(ws) if r['event'] == 'ase_reconsideration_boundary']
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    scripted(client, monkeypatch, [('Route discrepancy.', 'intervene', {'message': 'Check route response.'})])
    assert monitor.review('Later').kind == 'local_intervened'
    sends = scripted(client, monkeypatch, [
        ('', 'wait', {'after_turns': 1, 'mode': 'patrol'}),
        ('', 'wait', {'after_turns': 1, 'mode': 'patrol'}),
    ])
    assert monitor.review('Release').payload['mode'] == 'patrol'
    assert len(sends) == 2
    assert len([r for r in rows(ws) if r['event'] == 'ase_reconsideration_boundary']) == 1


def test_initial_intervention_requires_reference_but_can_follow_write_in_same_review(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    submitted = []
    monitor.intervention_callback = lambda message: (submitted.append(message) or {
        'submission_id': 'initial-reminder', 'delivery': 'queued',
        'submitted_task_turn': 12, 'submitted_cursor': 0})
    sends = scripted(client, monkeypatch, [
        ('Observed route discrepancy.', 'intervene', {'message': 'Inspect route behavior.'}),
        ('', 'file_write', {'path': 'monitor/reference.md', 'content': 'Public route behavior matters.'}),
        ('Observed route discrepancy.', 'intervene', {'message': 'Inspect route behavior.'}),
    ])
    assert monitor.review('Initialization').kind == 'local_intervened'
    assert len(sends) == 3
    assert submitted == ['Inspect route behavior.']
    assert monitor.control_echo.pending_submission['submission_id'] == 'initial-reminder'
    assert monitor.control_echo.active_echo is None
    assert ws.resolve_read('monitor/reference.md').read_text(encoding='utf-8') == 'Public route behavior matters.'
    assert len([r for r in rows(ws) if r['event'] == 'ase_reference_initialization_pending']) == 1


@pytest.mark.parametrize('reference', [None, '', 'X' * (ASE_REFERENCE_MAX_CHARS + 1), b'\xff'])
def test_invalid_reference_blocks_all_task_control_without_state_changes(tmp_path, reference):
    monitor, _, ws = make_monitor(tmp_path)
    if isinstance(reference, bytes):
        ws.resolve_private('monitor/reference.md').write_bytes(reference)
    elif reference is not None:
        ws.write_text('monitor/reference.md', reference)  # Bypass file tools as code_run can.
    submitted = []
    monitor.intervention_callback = lambda message: submitted.append(message)
    for name, arguments in (
        ('intervene', {'message': 'Inspect the route.'}),
        ('wait', {'after_turns': 1, 'mode': 'patrol'}),
    ):
        result = monitor.dispatch(name, arguments)
        assert result.action is None and result.data['status'].startswith('reference_')
    handoff = root(monitor)
    monitor.frame_kind = 'root'
    monitor.root_frame_handoff = handoff
    monitor._seen_completion = handoff
    monitor.completion_pending = True
    result = monitor.dispatch('allow_complete', {})
    assert result.action is None and result.data['status'] == 'reference_invalid'
    assert not submitted and not monitor.control_echo.active
    assert monitor.control_echo.pending_submission is None
    assert not [r for r in rows(ws) if r['event'] == 'ase_reconsideration_boundary']
    assert len([r for r in rows(ws) if r['event'] == 'ase_reference_control_blocked']) == 3


def test_code_run_reference_mutation_is_rechecked_before_control(tmp_path):
    monitor, _, ws = make_monitor(tmp_path)
    monitor.dispatch('file_write', {'path': 'monitor/reference.md',
                                    'content': 'Initial full task reference.'})
    monitor._ase_initialization_complete = True
    submitted = []
    monitor.intervention_callback = lambda message: (submitted.append(message) or
                                                     {'submission_id': 'sent', 'delivery': 'queued'})

    def change(value):
        result = monitor.dispatch('code_run', {
            'code': f'from pathlib import Path\nPath("reference.md").write_text({value!r}, encoding="utf-8")',
            'type': 'python', 'wait_seconds': 5})
        assert result.data['status'] == 'success'

    change('')
    assert monitor.dispatch('wait', {'mode': 'follow', 'after_turns': 1}).action is None
    assert monitor.dispatch('intervene', {'message': 'Check route.'}).action is None
    change('Z' * (ASE_REFERENCE_MAX_CHARS + 1))
    assert monitor.dispatch('intervene', {'message': 'Check route.'}).action is None
    assert not submitted and not monitor.control_echo.active
    change('A valid model-owned revision from ordinary code_run.')
    assert reference_surface(ws)[1]['status'] == 'present'
    assert monitor.dispatch('intervene', {'message': 'Check route.'}).action.kind == 'local_intervened'
    assert submitted == ['Check route.']
    assert monitor.control_echo.pending_submission['message'] == 'Check route.'


@pytest.mark.skip(reason='Persistent LocalContinuity episode retired; one-cycle Echo tested separately')
def test_intervention_anchor_survives_follows_then_patrol_clears(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Route response is the public requirement.')
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    sends = scripted(client, monkeypatch, [
        ('Route may be wrong.', 'intervene', {'message': 'Check actual route response.'}),
    ])
    assert monitor.review('Wake').kind == 'local_intervened'
    sends = scripted(client, monkeypatch, [
        ('Await first edit.', 'wait', {'mode': 'follow', 'after_turns': 2}),
    ])
    assert monitor.review('New Task feedback').kind == 'wait'
    assert 'Check actual route response.' in visible(sends[0])
    assert visible(sends[0]).index('Supervisor Reference') < visible(sends[0]).index('Local Control Continuity')
    assert visible(sends[0]).index('Local Control Continuity') < visible(sends[0]).index('Supervisory Situation')
    assert monitor.cqs.anchor['message'] == 'Check actual route response.'
    for reason in ('Await test', 'Await result'):
        sends = scripted(client, monkeypatch, [
            (reason, 'wait', {'mode': 'follow', 'after_turns': 2}),
        ])
        assert monitor.review('Next feedback').kind == 'wait'
        assert 'Check actual route response.' in visible(sends[0])
        assert monitor.cqs.anchor['message'] == 'Check actual route response.'
    assert monitor.cqs.follow['reason'] == 'Await result'
    assert monitor.cqs.follow_count == 3
    follow_events = [r for r in rows(ws) if r['event'] == 'ase_continuity_updated'
                     and r['source'] == 'wait_follow']
    assert [r['follow_count'] for r in follow_events] == [1, 2, 3]
    assert all(r['requested_after_turns'] == 2 for r in follow_events)
    sends = scripted(client, monkeypatch, [
        ('', 'wait', {'mode': 'patrol', 'after_turns': 2}),
        ('', 'wait', {'mode': 'patrol', 'after_turns': 2}),
    ])
    assert monitor.review('Release').payload['mode'] == 'patrol'
    assert 'Check actual route response.' in visible(sends[0])
    assert monitor.cqs.anchor is None and monitor.cqs.follow is None
    assert len([r for r in rows(ws) if r['event'] == 'ase_continuity_cleared']) == 1
    assert [r for r in rows(ws) if r['event'] == 'ase_reconsideration_boundary']


def test_release_boundary_root_and_changed_control(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Public route behavior matters.')
    handoff = root(monitor)
    sends = scripted(client, monkeypatch, [
        ('', 'allow_complete', {}),
        ('', 'file_read', {'path': 'task/workspace/router.py'}),
        ('', 'allow_complete', {}),
    ])
    action = monitor.review('Root', completion_pending=True, root_handoff=handoff)
    assert action.kind == 'allow_complete' and len(sends) == 3
    assert ROOT_SYSTEM_PROMPT not in sends[0]['system']
    assert 'monitor/root_working/' not in visible(sends[0])
    assert 'monitor/audit/root_frames/' not in visible(sends[0])
    assert monitor.root_routed and not monitor.verification_loop_v0
    events = rows(ws)
    assert len([r for r in events if r['event'] == 'ase_reconsideration_boundary']) == 1
    assert len([r for r in events if r['event'] == 'ase_release_confirmed']) == 1
    assert len([r for r in events if r['event'] == 'ase_post_boundary_tool' and r['tool_name'] == 'file_read']) == 1
    first_result = next(r for r in events if r['event'] == 'tool_result' and
                        r['data'] and r['data'].get('status') == 'release_not_executed')
    assert 'material state' not in first_result['data']['message']
    assert 'has not executed' in first_result['data']['message']
    assert 'scope' not in first_result['data']
    assert first_result['action'] is None
    assert [r for r in events if r['event'] == 'ase_reconsideration_boundary'][0]['visible_context']['reference_surface_sha256']


def test_boundary_can_change_to_follow(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Route response is the public requirement.')
    monitor.control_echo.note_submission('Check route behavior.', {
        'submission_id': 'old', 'submitted_task_turn': 12, 'submitted_cursor': 1})
    assert monitor.control_echo.reconcile_receipt({
        'submission_id': 'old', 'delivered': True,
        'delivery_kind': 'handed_to_task_interrupt_interface'}) == 'delivered'
    sends = scripted(client, monkeypatch, [
        ('', 'wait', {'mode': 'patrol', 'after_turns': 1}),
        ('Need response.', 'wait', {'mode': 'follow', 'after_turns': 1}),
    ])
    assert monitor.review('Wake').payload['mode'] == 'follow'
    assert len(sends) == 2
    assert any(r['event'] == 'ase_release_abandoned' and r['disposition'] == 'changed_to_follow'
               for r in rows(ws))
    assert monitor.control_echo.active_echo is None
    assert monitor.control_echo.pending_submission is None


def test_boundary_can_change_to_intervene(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Route response is the public requirement.')
    monitor.control_echo.note_submission('Check route behavior.', {
        'submission_id': 'old', 'submitted_task_turn': 12, 'submitted_cursor': 1})
    assert monitor.control_echo.reconcile_receipt({
        'submission_id': 'old', 'delivered': True,
        'delivery_kind': 'handed_to_task_interrupt_interface'}) == 'delivered'
    submitted = []
    monitor.intervention_callback = lambda message: (submitted.append(message) or {
        'submission_id': 'new', 'delivery': 'queued',
        'submitted_task_turn': 12, 'submitted_cursor': 1})
    scripted(client, monkeypatch, [
        ('', 'wait', {'mode': 'patrol', 'after_turns': 1}),
        ('Now correct it.', 'intervene', {'message': 'Fix route handling.'}),
    ])
    assert monitor.review('Wake').kind == 'local_intervened'
    assert any(r['event'] == 'ase_release_abandoned' and r['disposition'] == 'intervened'
               for r in rows(ws))
    assert submitted == ['Fix route handling.']
    assert monitor.control_echo.active_echo is None
    assert monitor.control_echo.pending_submission['submission_id'] == 'new'


def test_continuation_only_rewrites_working_and_legacy_paths_unchanged(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path / 'ase')
    ws.write_text('monitor/reference.md', 'PERMANENT_REFERENCE')
    before = ws.resolve_read('monitor/reference.md').read_bytes()
    monkeypatch.setattr(client, '_request_once', lambda tools: ([{'type': 'text',
        'text': 'Local continuation note only.'}], {}))
    monitor._prepare_continuation()
    assert ws.resolve_read('monitor/reference.md').read_bytes() == before
    assert ws.resolve_read('monitor/working.md').read_text(encoding='utf-8') == 'Local continuation note only.'
    legacy, legacy_client, _ = make_monitor(tmp_path / 'legacy', ase=False, cqs=True)
    disabled, disabled_client, _ = make_monitor(tmp_path / 'disabled', ase=False, cqs=True)
    disabled_client.config.pop('monitor_adaptive_supervisory_environment')
    assert legacy.system_prompt == disabled.system_prompt
    assert legacy.cqs.__class__ == disabled.cqs.__class__
    assert legacy.dcm.__class__ == disabled.dcm.__class__
    with pytest.raises(ValueError):
        make_monitor(tmp_path / 'bad', ase=True, cqs=True)


def test_exact_duplicate_telemetry_is_mechanical_and_not_a_control_trigger(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Route response is the public requirement.')
    sends = scripted(client, monkeypatch, [
        ('', 'file_read', {'path': 'task/workspace/router.py'}),
        ('', 'file_read', {'path': 'task/workspace/router.py', 'start': 1, 'count': 200}),
        ('', 'code_run', {'code': 'print(1)', 'type': 'python'}),
        ('', 'code_run', {'code': 'print(1)', 'type': 'python'}),
        ('', 'wait', {'mode': 'follow', 'after_turns': 3}),
    ])
    assert monitor.review('Wake').payload['mode'] == 'follow'
    assert len(sends) == 5
    duplicate = [r for r in rows(ws) if r['event'] == 'ase_exact_duplicate_observation_call']
    assert [r['tool_name'] for r in duplicate] == ['file_read', 'code_run']
    assert all(r['count'] == 2 for r in duplicate)
    assert not [r for r in rows(ws) if r['event'] == 'ase_reconsideration_boundary']


def test_failed_provider_request_does_not_claim_reference_exposure(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Task reference from Supervisor.')
    original = client._request_with_recovery

    def transport_failure(_tools):
        raise RuntimeError('offline transport failure')

    monkeypatch.setattr(client, '_request_with_recovery', transport_failure)
    with pytest.raises(RuntimeError, match='offline transport failure'):
        monitor.review('Wake')
    assert [r for r in rows(ws) if r['event'] == 'ase_reference_surface_prepared']
    assert not [r for r in rows(ws) if r['event'] == 'ase_context_injected']
    monkeypatch.setattr(client, '_request_with_recovery', original)
    sends = scripted(client, monkeypatch, [('', 'wait', {'mode': 'follow', 'after_turns': 1})])
    assert monitor.review('Fresh wake').kind == 'wait'
    assert 'Task reference from Supervisor.' in visible(sends[0])
    assert len([r for r in rows(ws) if r['event'] == 'ase_context_injected']) == 1


@pytest.mark.skip(reason='Persistent episode state retired; absence of Echo covered by candidate tests')
def test_follow_without_intervention_does_not_create_episode(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Public route behavior matters.')
    sends = scripted(client, monkeypatch, [('Watch progress.', 'wait',
                                           {'mode': 'follow', 'after_turns': 2})])
    assert monitor.review('Initialization').kind == 'wait'
    assert not monitor.cqs.active and monitor.cqs.episode_start_turn is None
    assert monitor.cqs.follow is None and monitor.cqs.completed_follow_cycles == 0
    scripted(client, monkeypatch, [('', 'wait', {'mode': 'patrol', 'after_turns': 2})])
    assert monitor.review('Later').kind == 'wait'
    assert not [r for r in rows(ws) if r['event'] == 'ase_reconsideration_boundary']
    assert 'Local Control Continuity' not in visible(sends[0])


def test_local_intervention_ends_review_once_then_feedback_is_seen(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Public route behavior matters.')
    delivered = []
    monitor.intervention_callback = lambda message: (delivered.append(message) or
                                                     {'submission_id': 'one', 'delivery': 'queued'})
    snapshots = []

    def offline_once(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        if len(snapshots) == 1:
            return ([{'type': 'tool_use', 'id': 'observe', 'name': 'file_read',
                      'input': {'path': 'task/workspace/router.py'}}], {})
        return ([{'type': 'text', 'text': 'Observed route conflict.'},
                 {'type': 'tool_use', 'id': 'send', 'name': 'intervene',
                  'input': {'message': 'Inspect route response.'}},
                 {'type': 'tool_use', 'id': 'not-run', 'name': 'file_write',
                  'input': {'path': 'monitor/unwanted.md', 'content': 'must not run'}}], {})

    monkeypatch.setattr(client, '_request_once', offline_once)
    action = monitor.review('Local wake')
    assert action.kind == 'local_intervened' and len(snapshots) == 2
    assert delivered == ['Inspect route response.']
    assert not (ws.private_root / 'unwanted.md').exists()
    assert any(r['event'] == 'control_result' and any(
        'not_executed' in item['content'] for item in r['results']) for r in rows(ws))
    assert monitor.control_echo.pending_submission['submission_id'] == 'one'
    assert monitor.control_echo.active_echo is None


@pytest.mark.skip(reason='Experimental episode/meta-regulation intentionally absent in Curator-Supervisor')
def test_episode_economy_reorientation_and_patrol(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path, meta=True)
    ws.write_text('monitor/reference.md', 'Public route behavior matters.')
    used = [10]
    monitor.task_budget_state = lambda: (used[0], 300)
    monitor.intervention_callback = lambda message: {'submission_id': message, 'delivery': 'queued'}
    scripted(client, monkeypatch, [('Initial concern.', 'intervene',
                                    {'message': 'Check route response.'})])
    assert monitor.review('Initial').kind == 'local_intervened'
    assert monitor.cqs.episode_start_turn == 10 and monitor.cqs.intervention_count == 1
    monkeypatch.setattr(monitor.analysis, 'start', lambda *args: {'status': 'success',
                                                                 'exit_code': 0})
    used[0] = 15
    scripted(client, monkeypatch, [
        ('', 'file_read', {'path': 'task/workspace/router.py'}),
        ('', 'file_read', {'path': 'task/workspace/router.py'}),
        ('', 'code_run', {'code': 'print(1)', 'type': 'python'}),
        ('', 'code_run', {'code': 'print(1)', 'type': 'python'}),
        ('Await edit.', 'wait', {'mode': 'follow', 'after_turns': 2}),
    ])
    assert monitor.review('Feedback 1').kind == 'wait'
    assert (monitor.cqs.file_read_count, monitor.cqs.code_run_count,
            monitor.cqs.duplicate_count) == (2, 2, 2)
    assert monitor.cqs.observation_trace[-1]['status'] == 'success'
    used[0] = 20
    scripted(client, monkeypatch, [('Await result.', 'wait', {'mode': 'follow', 'after_turns': 2})])
    assert monitor.review('Feedback 2').kind == 'wait'
    assert monitor.cqs.completed_follow_cycles == 1
    used[0] = 41
    sends = scripted(client, monkeypatch, [('Revision.', 'intervene',
                                           {'message': 'Recheck route response.'})])
    assert monitor.review('Feedback 3').kind == 'local_intervened'
    assert 'Control Reorientation' in visible(sends[0])
    assert 'Control episode: age=31 task turns' in visible(sends[0])
    assert 'Recent Supervisor observations (mechanical):' in visible(sends[0])
    assert monitor.cqs.episode_start_turn == 10
    assert monitor.cqs.latest_intervention_turn == 41
    assert monitor.cqs.intervention_count == 2
    assert monitor.cqs.completed_follow_cycles == 2
    events = rows(ws)
    assert len([r for r in events if r['event'] == 'ase_meta_regulation_eligible']) == 1
    assert [r for r in events if r['event'] == 'ase_meta_regulation_surface_injected'
            and r['eligible'] and r['trace_count'] > 0]
    assert len([r for r in events if r['event'] == 'ase_episode_observation']) == 4
    sends = scripted(client, monkeypatch, [
        ('', 'wait', {'mode': 'patrol', 'after_turns': 2}),
        ('', 'wait', {'mode': 'patrol', 'after_turns': 2}),
    ])
    assert monitor.review('Release').payload['mode'] == 'patrol'
    assert 'Control Reorientation' in visible(sends[0])
    assert not monitor.cqs.active and monitor.cqs.intervention_count == 0
    assert monitor.cqs.completed_follow_cycles == 0
    assert [r for r in rows(ws) if r['event'] == 'ase_control_episode_ended']


@pytest.mark.skip(reason='Persistent episode model-visible context intentionally replaced by Echo')
def test_root_intervention_keeps_existing_root_action_and_episode_context(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Public route behavior matters.')
    monitor.intervention_callback = lambda message: {'submission_id': 'root-one', 'delivery': 'queued'}
    scripted(client, monkeypatch, [('Local concern.', 'intervene',
                                    {'message': 'Inspect response.'})])
    assert monitor.review('Local').kind == 'local_intervened'
    handoff = root(monitor)
    sends = scripted(client, monkeypatch, [('Root concern.', 'intervene',
                                           {'message': 'Check final behavior.'})])
    action = monitor.review('Root', completion_pending=True, root_handoff=handoff)
    assert action.kind == 'root_intervened'
    assert 'Local Control Continuity' in visible(sends[0])
    assert 'Control episode:' not in visible(sends[0])
    assert 'Inspect response.' in visible(sends[0])
    assert monitor.cqs.intervention_count == 2
    assert monitor.cqs.anchor['message'] == 'Check final behavior.'


@pytest.mark.skip(reason='Episode telemetry intentionally removed from Curator-Supervisor')
def test_default_core_keeps_episode_telemetry_out_of_model_context(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    assert 'monitor_ase_meta_regulation' not in client.config
    assert monitor.ase_meta_regulation is False
    ws.write_text('monitor/reference.md', 'Public route behavior matters.')
    monitor.intervention_callback = lambda message: {'submission_id': message, 'delivery': 'queued'}
    used = [10]
    monitor.task_budget_state = lambda: (used[0], 300)
    scripted(client, monkeypatch, [('Concern.', 'intervene', {'message': 'Check response.'})])
    assert monitor.review('Initial').kind == 'local_intervened'
    used[0] = 15
    scripted(client, monkeypatch, [('', 'file_read', {'path': 'task/workspace/router.py'}),
                                   ('Await edit.', 'wait', {'mode': 'follow', 'after_turns': 2})])
    assert monitor.review('Feedback 1').kind == 'wait'
    used[0] = 20
    scripted(client, monkeypatch, [('Await result.', 'wait', {'mode': 'follow', 'after_turns': 2})])
    assert monitor.review('Feedback 2').kind == 'wait'
    used[0] = 30
    sends = scripted(client, monkeypatch, [('Continue.', 'wait',
                                            {'mode': 'follow', 'after_turns': 2})])
    assert monitor.review('Feedback 3').kind == 'wait'
    shown = visible(sends[0])
    assert 'Check response.' in shown and 'Await result.' in shown
    assert not any(marker in shown for marker in (
        'Control episode:', 'Recent Supervisor observations', 'Control Reorientation'))
    assert monitor.cqs.completed_follow_cycles == 2
    assert monitor.cqs.file_read_count == 1
    events = rows(ws)
    assert [r for r in events if r['event'] == 'ase_meta_regulation_eligible'
            and r['exposure_enabled'] is False]
    assert not [r for r in events if r['event'] == 'ase_meta_regulation_surface_injected']
    assert [r for r in events if r['event'] == 'ase_control_episode_observed'
            and r['file_read_count'] == 1]


def test_ase_intervention_history_boundaries_are_complete(tmp_path, monkeypatch):
    monitor, client, ws = make_monitor(tmp_path)
    ws.write_text('monitor/reference.md', 'Public route behavior matters.')
    # Runtime installs these names only for ASE live-intervention reviews.
    client.CONTROL_ACTIONS = ASE_CONTROL_ACTIONS
    submitted = []
    monitor.intervention_callback = lambda message: (submitted.append(message) or
                                                     {'submission_id': message, 'delivery': 'queued'})
    scripted(client, monkeypatch, [('Local concern.', 'intervene',
                                    {'message': 'Inspect response.'})])
    assert monitor.review('Local').kind == 'local_intervened'
    assert client._review_boundaries()[-1] == len(client.history)
    local_count = len(client._review_boundaries())
    handoff = root(monitor)
    scripted(client, monkeypatch, [('Root concern.', 'intervene',
                                    {'message': 'Inspect final response.'})])
    assert monitor.review('Root', completion_pending=True, root_handoff=handoff).kind == 'root_intervened'
    assert len(client._review_boundaries()) == local_count + 1
    assert client._review_boundaries()[-1] == len(client.history)
    assert submitted == ['Inspect response.', 'Inspect final response.']


def test_meta_requires_ase_and_boolean_config(tmp_path):
    with pytest.raises(ValueError, match='requires ASE'):
        make_monitor(tmp_path / 'legacy', ase=False, meta=True)
    with pytest.raises(ValueError, match='must be a boolean'):
        make_monitor(tmp_path / 'wrong', meta='true')
