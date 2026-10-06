"""Deterministic Curator-Supervisor contract checks; no provider or Task calls."""

import hashlib
import json
import queue
import threading
import time
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from monitor_agent_core.actions import MonitorAction
from monitor_agent_core.agent import MONITOR_TOOLS, MonitorAgent
from monitor_agent_core.ase_v0 import (ASE_REFERENCE_MAX_CHARS, ControlEcho,
                                       ReconsiderationBoundary, SYSTEM_PROMPT,
                                       reference_surface)
from monitor_agent_core.cfs_v0 import SituationState
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.runtime import ASEFeedbackBarrier, MonitorRuntime
from monitor_agent_core.workspace import MonitorWorkspace


def fixture_monitor(tmp_path):
    evidence, task = tmp_path / 'evidence', tmp_path / 'task'
    evidence.mkdir()
    task.mkdir()
    (evidence / 'original_task.txt').write_text('Preserve the public route.', encoding='utf-8')
    (evidence / 'public_events.jsonl').write_text('', encoding='utf-8')
    (task / 'route.py').write_text('ROUTE = True\n', encoding='utf-8')
    workspace = MonitorWorkspace(evidence, tmp_path / 'private', task_mounts={'workspace': task})
    client = MonitorProviderClient('anthropic', {
        'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
        'max_retries': 0, 'monitor_adaptive_supervisory_environment': True})
    monitor = MonitorAgent(client, workspace)
    monitor.task_budget_state = lambda: (8, 300)
    return monitor, client, workspace


@pytest.mark.parametrize('live', [None, True])
def test_curator_startup_accepts_default_or_explicit_live_intervention(tmp_path, live):
    monitor, client, _ = fixture_monitor(tmp_path)
    if live is not None:
        client.config['monitor_live_intervention'] = live
        monitor = MonitorAgent(client, monitor.workspace)
    assert monitor.control_echo is not None


def test_curator_startup_rejects_non_live_before_provider_request(tmp_path, monkeypatch):
    monitor, client, workspace = fixture_monitor(tmp_path)
    client.config['monitor_live_intervention'] = False
    monkeypatch.setattr(client, '_request_once', lambda *_: pytest.fail('provider request must not begin'))
    with pytest.raises(ValueError, match='requires monitor_live_intervention=true'):
        MonitorAgent(client, workspace)


def audit_rows(workspace):
    path = workspace.private_root / 'audit' / 'dialogue.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def submission(identity='s1', message='Remember the public route.'):
    return {'submission_id': identity, 'message': message,
            'submitted_task_turn': 8, 'submitted_cursor': 10}


def deliver(identity='s1', success=True):
    return {'submission_id': identity, 'delivered': success,
            'delivery_kind': 'handed_to_task_interrupt_interface' if success else 'failed',
            'error_type': None if success else 'RuntimeError',
            'delivery_task_turn': 8, 'delivery_cursor': 10}


def test_task_book_full_exposure_guard_and_prompt_semantics(tmp_path):
    monitor, _, workspace = fixture_monitor(tmp_path)
    assert 'Task Book' in SYSTEM_PROMPT and 'not verified truth or current-world proof' in SYSTEM_PROMPT
    assert 'progress or completion ledger' in SYSTEM_PROMPT
    assert 'Task Book' in reference_surface(workspace)[0]
    assert monitor.dispatch('wait', {'after_turns': 1}).data['status'] == 'reference_initialization_pending'
    text = 'HEAD' + 'x' * 8000 + 'MIDDLE_SENTINEL' + 'y' * 7000 + 'TAIL'
    assert monitor.dispatch('file_write', {'path': 'monitor/reference.md', 'content': text}).data['characters'] == len(text)
    surface, meta = reference_surface(workspace)
    assert text in surface and 'MIDDLE_SENTINEL' in surface and meta['truncated'] is False
    assert meta['source_characters'] == len(text) and meta['status'] == 'present'
    assert monitor.dispatch('file_patch', {'path': 'monitor/reference.md',
                                          'old_text': 'HEAD', 'new_text': 'START'}).data.get('status') != 'error'
    before = workspace.resolve_read('monitor/reference.md').read_bytes()
    assert monitor.dispatch('file_write', {'path': 'monitor/reference.md',
                                          'content': 'x' * (ASE_REFERENCE_MAX_CHARS + 1)}).data['status'] == 'error'
    assert workspace.resolve_read('monitor/reference.md').read_bytes() == before
    assert [r for r in audit_rows(workspace) if r['event'] == 'curator_task_book_mutated']


@pytest.mark.parametrize('invalid', [None, '', b'\xff', 'x' * (ASE_REFERENCE_MAX_CHARS + 1)])
def test_invalid_task_book_blocks_control_even_after_direct_mutation(tmp_path, invalid):
    monitor, _, workspace = fixture_monitor(tmp_path)
    monitor.intervention_callback = lambda _: pytest.fail('invalid Book must not deliver')
    path = workspace.private_root / 'reference.md'
    if invalid is not None:
        path.write_bytes(invalid if isinstance(invalid, bytes) else invalid.encode())
    assert monitor.dispatch('intervene', {'message': 'A reminder.'}).data['status'] == 'reference_invalid'
    assert monitor.dispatch('wait', {'after_turns': 1}).action is None
    handoff = {'generation': 1, 'request_id': 'completion-1', 'cursor': 1}
    monitor.completion_state = lambda: handoff
    monitor._seen_completion = handoff
    monitor.root_frame_handoff = handoff
    monitor.frame_kind = 'root'
    assert monitor.dispatch('allow_complete', {}).action is None
    assert monitor.control_echo.pending_submission is None
    path.write_text('Durable route contract.', encoding='utf-8')
    monitor.completion_state = lambda: None
    monitor.frame_kind = 'local'
    assert monitor.dispatch('wait', {'after_turns': 1}).action.kind == 'wait'


def test_no_semantic_task_book_checker_or_extra_tools(tmp_path):
    monitor, _, workspace = fixture_monitor(tmp_path)
    workspace.write_text('monitor/reference.md', 'Target 1 complete. 6/7 done.')
    assert monitor.dispatch('wait', {'after_turns': 1}).action.kind == 'wait'
    assert [tool['function']['name'] for tool in MONITOR_TOOLS] == [
        'file_read', 'file_write', 'file_patch', 'code_run', 'wait', 'intervene', 'allow_complete']
    assert monitor.cqs is None and monitor.control_echo is not None
    assert monitor.situation.include_supervisory_control is False


def test_echo_queue_delivery_failure_stale_and_duplicate_are_mechanical():
    events = []
    echo = ControlEcho(lambda event, **facts: events.append((event, facts)))
    echo.begin_review('r1')
    echo.observe({'review_id': 'r1', 'event': 'tool_call', 'name': 'intervene'}, 7)
    echo.note_submission(submission()['message'], submission())
    assert echo.pending_submission and echo.active_echo is None and echo.render() is None
    assert echo.reconcile_receipt(deliver('wrong')) == 'stale'
    assert echo.pending_submission and echo.active_echo is None
    assert echo.reconcile_receipt(deliver(success=False)) == 'failed'
    assert echo.pending_submission is None and echo.active_echo is None
    assert echo.reconcile_receipt(deliver()) == 'stale'
    echo.note_submission(submission()['message'], submission())
    assert echo.reconcile_receipt(deliver()) == 'delivered'
    assert echo.reconcile_receipt(deliver()) == 'stale'
    assert echo.active_echo['action_locator'] == 'monitor/audit/dialogue.jsonl#7'
    assert echo.active_echo['submitted_task_turn'] == 8
    assert [name for name, _ in events].count('curator_echo_delivery_confirmed') == 1


def test_echo_visible_only_after_delivery_then_one_successful_rejudgment(tmp_path):
    monitor, _, workspace = fixture_monitor(tmp_path)
    workspace.write_text('monitor/reference.md', 'Durable route contract.')
    echo = monitor.control_echo
    echo.note_submission(submission()['message'], submission())
    assert 'Control Echo' not in monitor._active_working_context()
    assert echo.reconcile_receipt(deliver()) == 'delivered'
    echo.begin_review('r1')
    monitor.review_id = 'r1'
    monitor.situation.begin_review('r1')
    context = monitor._active_working_context()
    assert context.index('Task Book') < context.index('Control Echo') < context.index('Supervisory Situation')
    assert 'actually delivered' in context and 'not task truth' in context
    monitor._cfs_context_appended()  # A successful provider response exposed the context.
    assert echo.visible_review_id == 'r1'
    echo.complete_review(MonitorAction('root_route', {}))
    assert echo.active
    echo.complete_review(None)  # Provider failure / review exhaustion has no terminal control.
    assert echo.active
    echo.complete_review(MonitorAction('wait', {'mode': 'follow'}))
    assert not echo.active and echo.pending_submission is None
    assert [r for r in audit_rows(workspace) if r['event'] == 'curator_echo_consumed']


@pytest.mark.parametrize('kind', ['wait', 'local_intervened', 'root_intervened', 'allow_complete'])
def test_terminal_actions_consume_visible_echo_and_new_delivery_replaces(kind):
    echo = ControlEcho(lambda *_args, **_fields: None)
    echo.note_submission('Old reminder.', submission())
    echo.reconcile_receipt(deliver())
    echo.begin_review('r1')
    assert echo.render()
    echo.surface_visible()
    if kind in {'local_intervened', 'root_intervened'}:
        echo.note_submission('New reminder.', submission('s2', 'New reminder.'))
    echo.complete_review(MonitorAction(kind, {}))
    assert echo.active_echo is None
    if kind in {'local_intervened', 'root_intervened'}:
        assert echo.pending_submission['submission_id'] == 's2'
        echo.reconcile_receipt(deliver('s2'))
        assert echo.active_echo['message'] == 'New reminder.'


def test_echo_not_consumed_when_provider_did_not_expose_surface():
    echo = ControlEcho(lambda *_args, **_fields: None)
    echo.note_submission('Reminder.', submission())
    echo.reconcile_receipt(deliver())
    echo.begin_review('r1')
    echo.render()
    echo.complete_review(MonitorAction('wait', {}))
    assert echo.active
    echo.begin_review('r2')
    echo.render()
    echo.surface_visible()
    echo.complete_review(MonitorAction('wait', {}))
    assert not echo.active


def test_active_echo_patrol_keeps_existing_two_turn_release_boundary(tmp_path, monkeypatch):
    monitor, client, workspace = fixture_monitor(tmp_path)
    workspace.write_text('monitor/reference.md', 'Durable route contract.')
    monitor.control_echo.note_submission('A delivered reminder.', submission())
    monitor.control_echo.reconcile_receipt(deliver())
    requests = []

    def offline_once(tools):
        requests.append(client.assembled_request_snapshot(tools))
        return ([{'type': 'tool_use', 'id': f'wait-{len(requests)}', 'name': 'wait',
                  'input': {'after_turns': 1, 'mode': 'patrol'}}], {})

    monkeypatch.setattr(client, '_request_once', offline_once)
    action = monitor.review('New genuine Task feedback.')
    assert action.kind == 'wait' and action.payload['mode'] == 'patrol'
    assert len(requests) == 2 and not monitor.control_echo.active
    assert 'A delivered reminder.' in json.dumps(requests[0]['messages'], ensure_ascii=False)
    assert len([r for r in audit_rows(workspace) if r['event'] == 'ase_reconsideration_boundary']) == 1
    assert len([r for r in audit_rows(workspace) if r['event'] == 'curator_echo_consumed']) == 1


def test_delivery_barrier_requires_new_task_model_turn_and_cursor():
    events = []
    echo = ControlEcho(lambda event, **facts: events.append(event))
    barrier = ASEFeedbackBarrier(lambda event, **facts: events.append(event))
    echo.note_submission('Reminder.', submission())
    assert barrier.pending is None
    assert echo.pending_submission is not None  # Delivery-pending wake must block.
    echo.reconcile_receipt(deliver())
    barrier.start(task_turn=echo.active_echo['submitted_task_turn'],
                  cursor=echo.active_echo['submitted_cursor'], submission_id='s1')
    assert not barrier.permits(task_turn=8, cursor=11, model_feedback_turn=8, model_feedback_cursor=11)
    assert not barrier.permits(task_turn=9, cursor=12, model_feedback_turn=8, model_feedback_cursor=11)
    assert not barrier.permits(task_turn=8, cursor=12, model_feedback_turn=9, model_feedback_cursor=12)
    assert barrier.permits(task_turn=9, cursor=12, model_feedback_turn=9, model_feedback_cursor=12)
    assert events.count('ase_feedback_barrier_started') == 1


def test_feedback_before_confirmed_delivery_cannot_satisfy_barrier():
    echo = ControlEcho(lambda *_args, **_fields: None)
    barrier = ASEFeedbackBarrier(lambda *_args, **_fields: None)
    echo.note_submission('Reminder.', submission())  # queued at turn 8, cursor 10
    receipt = dict(deliver(), delivery_task_turn=9, delivery_cursor=12)
    echo.reconcile_receipt(receipt)
    barrier.start(task_turn=echo.active_echo['delivered_task_turn'],
                  cursor=echo.active_echo['delivered_cursor'], submission_id='s1')
    assert not barrier.permits(task_turn=9, cursor=12,
                               model_feedback_turn=9, model_feedback_cursor=12)
    assert barrier.permits(task_turn=10, cursor=13,
                           model_feedback_turn=10, model_feedback_cursor=13)


def test_curator_situation_suppresses_control_only_in_visible_surface(tmp_path):
    monitor, _, workspace = fixture_monitor(tmp_path)
    monitor.situation.begin_review('r0')
    monitor.situation.build()
    monitor.situation.context_appended()
    monitor.situation.end_review(None)
    (workspace.task_mounts['workspace'] / 'new.go').write_text('new', encoding='utf-8')
    events = workspace.evidence_root / 'public_events.jsonl'
    events.write_text(json.dumps({'archive_sequence': 1, 'task_turn': 8,
                                  'boundary': 'post_model_pre_tool', 'text': 'Task proceeds.',
                                  'tool_calls': [{'id': 'code-1', 'name': 'code_run',
                                                  'args': {'script': 'go test ./...', 'cwd': '/app'}}],
                                  'tool_results': [{'tool_use_id': 'code-1', 'content': json.dumps({
                                      'status': 'success', 'exit_code': 0, 'stdout': 'ok'})}]}) + '\n',
                      encoding='utf-8')
    workspace.write_text('monitor/reference.md', 'Durable route contract.')
    (workspace.private_root / 'delivery_feedback.jsonl').write_text(
        json.dumps({'delivery': 'handed_to_task_interrupt_interface', 'message': 'OLD_REMINDER'}) + '\n',
        encoding='utf-8')
    monitor.situation.begin_review('r1')
    surface, meta = monitor.situation.build(
        handoff={'generation': 1, 'request_id': 'completion-1', 'cursor': 1},
        used_turns=8, max_turns=300, remaining_seconds=90)
    assert 'Task proceeds.' in surface and 'Task turns=8..8' in surface
    assert 'added: task/workspace/new.go' in surface
    assert 'go test ./...' in surface and 'exit_code=0' in surface
    assert 'Pending root handoff: generation=1' in surface
    assert 'remaining: 292' in surface and '90' in surface
    assert 'OLD_REMINDER' not in surface and 'Previous supervisory control' not in surface
    manifest = json.loads((workspace.private_root / 'audit/cfs_deltas' /
                           Path(meta['manifest_locator']).name).read_text(encoding='utf-8'))
    assert manifest['control']['latest_delivery']['message'] == 'OLD_REMINDER'
    ordinary = SituationState(workspace)
    ordinary.begin_review('r2')
    legacy_surface, _ = ordinary.build()
    assert 'Previous supervisory control' in legacy_surface


def test_root_reconsideration_and_frozen_source_files(tmp_path):
    monitor, _, workspace = fixture_monitor(tmp_path)
    workspace.write_text('monitor/reference.md', 'Durable route contract.')
    boundary = monitor.dcm
    assert isinstance(boundary, ReconsiderationBoundary)
    boundary.begin_review('root-review')
    boundary.model_turn = 1
    first = boundary.release('allow_complete', 'root', {})
    assert first['status'] == 'release_not_executed'
    boundary.model_turn = 2
    assert boundary.release('allow_complete', 'root', {}) is None
    root = Path(__file__).resolve().parents[2]
    for relative in ('GenericAgent-main/monitor_agent_core/provider.py',
                     'GenericAgent-main/monitor_agent_core/workspace.py',
                     'GenericAgent-main/monitor_agent_core/root_scope_v1.py',
                     'GenericAgent-main/monitor_agent_core/loop.py'):
        assert subprocess.run(['git', 'diff', '--quiet',
            '928af84d3d3ee85382d16b43c0f390fa0650e566', '--', relative],
            cwd=root, check=False).returncode == 0


def test_meta_regulation_is_explicitly_rejected(tmp_path):
    evidence, task = tmp_path / 'evidence', tmp_path / 'task'
    evidence.mkdir()
    task.mkdir()
    workspace = MonitorWorkspace(evidence, tmp_path / 'private', task_mounts={'workspace': task})
    client = MonitorProviderClient('anthropic', {'apikey': 'offline',
        'apibase': 'https://offline.invalid', 'model': 'offline',
        'monitor_adaptive_supervisory_environment': True, 'monitor_ase_meta_regulation': True})
    with pytest.raises(ValueError, match='not part of Curator-Supervisor'):
        MonitorAgent(client, workspace)


@pytest.mark.parametrize('delivery_succeeds', [True, False])
def test_worker_delivery_ack_precedes_barrier_and_echo(tmp_path, monkeypatch, delivery_succeeds):
    """The real worker/pump IPC path runs with deterministic, non-model stand-ins."""
    import monitor_agent_core.agent as agent_module
    import monitor_agent_core.provider as provider_module
    from monitor_agent_core.runtime import _worker

    reviews, audit, deliveries = [], [], []

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
            raise AssertionError('fixture worker must close normally')

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
            self.control_echo = ControlEcho(self._progress)

        def _progress(self, event, **fields):
            audit.append((event, fields))

        def review(self, _context, **_kwargs):
            self.control_echo.begin_review(f'r{len(reviews) + 1}')
            visible = self.control_echo.render()
            if visible:
                self.control_echo.surface_visible()
            reviews.append({'echo': visible, 'pending': self.control_echo.pending_submission is not None})
            if len(reviews) == 2:
                message = 'Remember the public route.'
                receipt = self.intervention_callback(message)
                self.control_echo.note_submission(message, receipt)
                action = MonitorAction('local_intervened', {})
            else:
                action = MonitorAction('wait', {'after_turns': 1, 'mode': 'patrol'})
            self.control_echo.complete_review(action)
            return action

    monkeypatch.setattr(provider_module, 'MonitorProviderClient', FakeClient)
    monkeypatch.setattr(agent_module, 'MonitorAgent', FakeMonitor)
    task = tmp_path / 'task'
    task.mkdir()

    def deliver_to_task(message):
        deliveries.append(message)
        if not delivery_succeeds:
            raise RuntimeError('fixture delivery failure')
        return 'task-mailbox-accepted'

    runtime = MonitorRuntime(public_task='Public route.', task_workspace=task,
                             artifact_dir=tmp_path / 'artifacts', config_name='offline',
                             model_config={'monitor_adaptive_supervisory_environment': True},
                             interrupt_callback=deliver_to_task, task_id='fixture:curator',
                             worker_target=_worker, process_factory=ThreadProcess)
    try:
        deadline = time.monotonic() + 5
        while not (runtime.artifact_dir / 'runtime_receipts.jsonl').exists():
            assert time.monotonic() < deadline
            time.sleep(.01)
        runtime.archive_boundary({'boundary': 'post_model_pre_tool', 'task_turn': 8,
                                  'text': 'First model response.'})
        while len(deliveries) < 1:
            assert time.monotonic() < deadline
            time.sleep(.01)
        runtime.archive_boundary({'boundary': 'post_tool_pre_next_llm', 'task_turn': 8,
                                  'text': 'Same-turn tool result.'})
        time.sleep(.05)
        assert len(reviews) == 2
        runtime.archive_boundary({'boundary': 'post_model_pre_tool', 'task_turn': 9,
                                  'text': 'New model feedback.'})
        while len(reviews) < 3:
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert deliveries == ['Remember the public route.']
        assert (reviews[2]['echo'] is not None) is delivery_succeeds
        assert [name for name, _ in audit].count('curator_echo_delivery_confirmed') == int(delivery_succeeds)
        assert [name for name, _ in audit].count('ase_feedback_barrier_started') == int(delivery_succeeds)
        assert [name for name, _ in audit].count('ase_feedback_barrier_satisfied') == int(delivery_succeeds)
        assert [name for name, _ in audit].count('curator_echo_delivery_failed') == int(not delivery_succeeds)
    finally:
        runtime.close()


def test_root_handoff_correction_receipt_activates_echo_only_when_matched(tmp_path, monkeypatch):
    import monitor_agent_core.agent as agent_module
    import monitor_agent_core.provider as provider_module
    from monitor_agent_core.runtime import _worker, _coalesce_wake_command
    import queue

    queued = queue.Queue()
    queued.put({'kind': 'boundary', 'cursor': 1, 'task_turn': 8})
    queued.put({'kind': 'delivery_receipt', 'cursor': 1, 'task_turn': 8})
    assert _coalesce_wake_command(queued, queued.get())['kind'] == 'delivery_receipt'
    assert queued.get()['kind'] == 'boundary'

    reviews, audit = [], []

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
            raise AssertionError('fixture worker must close normally')

    class FakeClient:
        def __init__(self, *_args):
            self.captured_root_handoffs = set()

    class FakeMonitor:
        ase_v0 = True
        dcec_enabled = False
        root_routed = True
        verification = None
        max_review_turns = 20

        def __init__(self, *_args, **_kwargs):
            self.control_echo = ControlEcho(self._progress)

        def _progress(self, event, **fields):
            audit.append((event, fields))

        def review(self, _context, completion_pending=False, **_kwargs):
            self.control_echo.begin_review(f'r{len(reviews) + 1}')
            visible = self.control_echo.render()
            if visible:
                self.control_echo.surface_visible()
            reviews.append({'root': completion_pending, 'echo': visible})
            if completion_pending:
                message = 'Revisit the whole public mission.'
                receipt = self.intervention_callback(message)
                self.control_echo.note_submission(message, receipt)
                action = MonitorAction('root_intervened', {})
            else:
                action = MonitorAction('wait', {'after_turns': 1, 'mode': 'patrol'})
            self.control_echo.complete_review(action)
            return action

    monkeypatch.setattr(provider_module, 'MonitorProviderClient', FakeClient)
    monkeypatch.setattr(agent_module, 'MonitorAgent', FakeMonitor)
    task = tmp_path / 'task'
    task.mkdir()
    runtime = MonitorRuntime(public_task='Whole public mission.', task_workspace=task,
                             artifact_dir=tmp_path / 'artifacts', config_name='offline',
                             model_config={'monitor_adaptive_supervisory_environment': True},
                             interrupt_callback=lambda _: pytest.fail('root correction is not a local interrupt'),
                             task_id='fixture:root', worker_target=_worker,
                             process_factory=ThreadProcess)
    try:
        deadline = time.monotonic() + 5
        receipts = runtime.artifact_dir / 'runtime_receipts.jsonl'
        while not (receipts.exists() and '"kind": "ready"' in receipts.read_text(encoding='utf-8')):
            assert time.monotonic() < deadline
            time.sleep(.01)
        outcome = runtime.request_completion({'boundary': 'task_control_handoff', 'task_turn': 8,
                                              'text': 'Completion proposed.'})
        assert not outcome.allow
        while not any(name == 'curator_echo_delivery_confirmed' for name, _ in audit):
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert reviews[1]['root'] and reviews[1]['echo'] is None
        runtime.archive_boundary({'boundary': 'post_model_pre_tool', 'task_turn': 9,
                                  'text': 'New Task model response.'})
        while len(reviews) < 3:
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert 'Revisit the whole public mission.' in reviews[2]['echo']
        assert [name for name, _ in audit].count('ase_feedback_barrier_started') == 1
        assert [name for name, _ in audit].count('curator_echo_consumed') == 1
    finally:
        runtime.close()


def test_late_unmatched_root_correction_receipt_does_not_activate_echo_or_barrier(tmp_path):
    """Exercise the parent's actual output pump with a superseded completion identity."""
    private = tmp_path / 'private'
    private.mkdir()
    received = []
    runtime = MonitorRuntime.__new__(MonitorRuntime)
    runtime._closed = threading.Event()
    runtime._correction_identity = None
    runtime._correction_deadline = 0
    runtime._outputs = queue.Queue()
    runtime._process = SimpleNamespace(is_alive=lambda: True)
    runtime._finish_correction = lambda: None
    runtime._pending_lock = threading.Lock()
    runtime._pending = {}  # Matching root request was superseded before this correction arrived.
    runtime._active_completion = SimpleNamespace(value=0)
    runtime._completion_receipts = queue.Queue()
    runtime._intervention_receipts = queue.Queue()
    runtime._commands = queue.Queue()
    runtime._latest_task_turn = SimpleNamespace(value=8)
    runtime._latest_public_cursor = SimpleNamespace(value=10)
    runtime.private_root = private
    runtime._append_receipt = lambda value: received.append(value)
    pump = threading.Thread(target=MonitorRuntime._pump_outputs, args=(runtime,), daemon=True)
    pump.start()
    try:
        echo = ControlEcho(lambda *_args, **_fields: None)
        echo.note_submission('Revisit the whole mission.', submission(
            identity='late-root', message='Revisit the whole mission.'))
        barrier = ASEFeedbackBarrier(lambda *_args, **_fields: None)
        runtime._outputs.put({'kind': 'completion', 'decision': 'continue',
                              'request_id': 'superseded-request', 'submission_id': 'late-root',
                              'control_submission': True, 'message': 'Revisit the whole mission.'})
        receipt = runtime._intervention_receipts.get(timeout=2)
        assert received[0]['delivery'] == 'archived_late_or_unmatched'
        assert receipt['submission_id'] == 'late-root'
        assert receipt['delivered'] is False
        assert receipt['delivery_kind'] == 'archived_late_or_unmatched'
        assert echo.reconcile_receipt(receipt) == 'failed'
        assert echo.active_echo is None
        assert echo.pending_submission is None
        assert barrier.pending is None
    finally:
        runtime._closed.set()
        pump.join(timeout=2)
        assert not pump.is_alive()
