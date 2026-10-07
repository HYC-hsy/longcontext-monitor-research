"""Zero-model checks for the optional, handoff-cumulative root turn ceiling."""

import multiprocessing as mp
import queue
import threading
import time

import pytest

from monitor_agent_core.actions import MonitorAction
from monitor_agent_core.loop import MonitorLoopError
from monitor_agent_core.runtime import (
    MonitorRuntime, _remaining_root_turns, _root_turn_ceiling, _worker,
)


class ThreadProcess:
    def __init__(self, target, args, daemon):
        self.thread = threading.Thread(target=target, args=args, daemon=daemon)

    def start(self):
        self.thread.start()

    def is_alive(self):
        return self.thread.is_alive()

    def join(self, timeout):
        self.thread.join(timeout)

    def terminate(self):
        raise AssertionError('Zero-model worker must close normally')


def test_runtime_root_option_is_explicit_and_default_is_ordinary(tmp_path):
    assert _root_turn_ceiling({}, 20) == 20
    assert _root_turn_ceiling({'root_max_review_turns': None}, 20) == 20
    assert _root_turn_ceiling({'root_max_review_turns': 300}, 20) == 300
    for invalid in (False, 0, -1, 3.0, '300'):
        with pytest.raises(ValueError, match='root_max_review_turns'):
            _root_turn_ceiling({'root_max_review_turns': invalid}, 20)

    captured = []

    def passive_worker(config, commands, outputs):
        captured.append((config['max_review_turns'], config['root_max_review_turns']))
        outputs.put({'kind': 'ready'})
        while commands.get()['kind'] != 'close':
            pass

    for index, root_limit in enumerate((None, 300)):
        workspace = tmp_path / f'workspace-{index}'
        workspace.mkdir()
        runtime = MonitorRuntime(
            task_id='fixture', public_task='Task', task_workspace=workspace,
            artifact_dir=tmp_path / f'audit-{index}', config_name='fixture',
            model_config={}, interrupt_callback=lambda _: None,
            max_review_turns=20, root_max_review_turns=root_limit,
            worker_target=passive_worker, process_factory=ThreadProcess)
        runtime.close()
    assert captured == [(20, None), (20, 300)]


def _scripted_worker(tmp_path, monkeypatch, root_limit, root_steps):
    from monitor_agent_core import agent, provider

    calls = []
    lifecycle = []
    local_seen = threading.Event()

    class Client:
        def __init__(self, *_args):
            self.captured_root_handoffs = set()

    class Contrast:
        def abandon(self, reason):
            lifecycle.append(('abandon', reason))

    class Monitor:
        def __init__(self, _client, _workspace, max_review_turns, **_kwargs):
            self.max_review_turns = max_review_turns
            self.dcec_enabled = False
            self.ase_v0 = False
            self.root_routed = True
            self.rer_v0 = True
            self.verification = None
            self.control_echo = None
            self.crs = Contrast()
            self.root_index = 0

        def review(self, _context, completion_pending=False, *, root_handoff=None,
                   max_turns_override=None, root_transition_view=None):
            calls.append((root_handoff is not None, max_turns_override,
                          self.max_review_turns))
            effective_limit = (self.max_review_turns if max_turns_override is None
                               else max_turns_override)
            if root_handoff is None:
                local_seen.set()
                return MonitorAction('wait', {'mode': 'follow', 'after_turns': 1})
            kind, used = root_steps[self.root_index]
            self.root_index += 1
            if kind == 'exhaust':
                assert used == effective_limit
                raise MonitorLoopError('Scripted review exhausted its exact turn allowance')
            if kind == 'root_reestimate':
                assert used <= effective_limit
                return MonitorAction(kind, {
                    'request_id': root_handoff['request_id'],
                    'generation': root_handoff['generation'],
                    'root_horizon_digest': f'horizon-{self.root_index}',
                    'model_turns_used_in_this_subreview': used,
                })
            assert kind == 'allow_complete' and used <= effective_limit
            return MonitorAction(kind, {
                'request_id': root_handoff['request_id'],
                'root_frame_generation': root_handoff['generation'],
            })

        def enter_root_reestimate(self, _handoff, _action):
            lifecycle.append(('entered', self.root_index))

        def restore_rer_parent(self, reason):
            lifecycle.append(('restored', reason))

    monkeypatch.setattr(agent, 'MonitorAgent', Monitor)
    monkeypatch.setattr(provider, 'MonitorProviderClient', Client)
    evidence = tmp_path / 'evidence'
    private = tmp_path / 'private'
    workspace = tmp_path / 'workspace'
    for path in (evidence, private, workspace):
        path.mkdir()
    active = mp.Value('q', 0)
    config = {
        'config_name': 'fixture', 'model_config': {}, 'task_id': 'fixture',
        'evidence_root': str(evidence), 'private_root': str(private),
        'task_workspace': str(workspace), 'max_review_turns': 20,
        'root_max_review_turns': root_limit,
        'stop_event': threading.Event(), 'active_completion': active,
        'completion_cursor': mp.Value('q', 1),
        'latest_task_turn': mp.Value('q', 1),
        'task_budget_turns_used': mp.Value('q', 1),
        'completion_receipts': queue.Queue(),
        'run_deadline_epoch': time.time() + 60,
    }
    commands, outputs = queue.Queue(), queue.Queue()
    worker = threading.Thread(target=_worker, args=(config, commands, outputs), daemon=True)
    worker.start()
    try:
        assert outputs.get(timeout=5)['kind'] == 'ready'
        assert local_seen.wait(5)
        commands.put({'kind': 'boundary', 'task_turn': 2, 'cursor': 1})
        deadline = time.monotonic() + 5
        while len(calls) < 2 and time.monotonic() < deadline:
            time.sleep(.01)
        assert len(calls) >= 2
        assert outputs.get(timeout=5)['kind'] == 'review_silent'
        active.value = 1
        commands.put({'kind': 'completion', 'generation': 1,
                      'request_id': 'completion-1', 'cursor': 1, 'task_turn': 1})
        result = outputs.get(timeout=5)
        if result['kind'] == 'completion':
            config['completion_receipts'].put({'request_id': 'completion-1',
                                               'accepted': False})
        return calls, lifecycle, result
    finally:
        config['stop_event'].set()
        commands.put({'kind': 'close'})
        worker.join(timeout=5)
        assert not worker.is_alive()


def test_local_stays_at_20_and_root_terminal_at_27_under_300(tmp_path, monkeypatch):
    calls, lifecycle, result = _scripted_worker(tmp_path, monkeypatch, 300, [
        ('root_reestimate', 4), ('root_reestimate', 12),
        ('allow_complete', 11),
    ])
    assert calls == [(False, None, 20), (False, None, 20),
                     (True, 300, 20), (True, 296, 20), (True, 284, 20)]
    assert lifecycle == [('entered', 1), ('entered', 2)]
    assert result['kind'] == 'completion' and result['decision'] == 'allow'


def test_multi_rer_restart_still_shares_one_300_ceiling(tmp_path, monkeypatch):
    calls, lifecycle, result = _scripted_worker(tmp_path, monkeypatch, 300, [
        ('root_reestimate', 4), ('root_reestimate', 12),
        ('root_reestimate', 30), ('allow_complete', 11),
    ])
    assert [limit for root, limit, _ in calls if root] == [300, 296, 284, 254]
    assert [event for event, _ in lifecycle] == ['entered', 'entered', 'entered']
    assert result['kind'] == 'completion' and result['decision'] == 'allow'


def test_root_exhaustion_at_300_fails_closed_and_cleans_rer(tmp_path, monkeypatch):
    calls, lifecycle, result = _scripted_worker(tmp_path, monkeypatch, 300, [
        ('root_reestimate', 4), ('root_reestimate', 12), ('exhaust', 284),
    ])
    assert [limit for root, limit, _ in calls if root] == [300, 296, 284]
    assert result['kind'] == 'failure' and result['completion'] is True
    assert ('abandon', 'runtime_error') in lifecycle
    assert ('restored', 'runtime_error') in lifecycle
    assert not any(event == 'allow_complete' for event, _ in lifecycle)


def test_unset_root_option_preserves_20_turn_root_budget(tmp_path, monkeypatch):
    calls, lifecycle, result = _scripted_worker(tmp_path, monkeypatch, None, [
        ('root_reestimate', 4), ('root_reestimate', 12), ('exhaust', 4),
    ])
    assert [limit for root, limit, _ in calls if root] == [None, 16, 4]
    assert result['kind'] == 'failure' and result['completion'] is True
    assert ('restored', 'runtime_error') in lifecycle


def test_subreview_debit_is_unchanged():
    assert _remaining_root_turns(300, MonitorAction(
        'root_route', {'prior_model_turns': 3})) == 297
    remaining = 300
    for consumed, expected in ((4, 296), (12, 284), (30, 254), (254, 0)):
        remaining = _remaining_root_turns(remaining, MonitorAction(
            'root_reestimate', {'model_turns_used_in_this_subreview': consumed}))
        assert remaining == expected
