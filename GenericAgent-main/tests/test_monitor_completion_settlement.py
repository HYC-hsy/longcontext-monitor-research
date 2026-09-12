"""Run the real worker and output pump with a deterministic model substitute."""
import threading
import time

import pytest

from monitor_agent_core.actions import MonitorAction
from monitor_agent_core.runtime import MonitorRuntime
from test_monitor_handoff_recovery import ThreadProcess


@pytest.mark.parametrize('stale', [False, True])
def test_approval_settlement_preserves_or_ends_observation(tmp_path, monkeypatch, stale):
    from monitor_agent_core import agent, provider
    entered, release, resumed = threading.Event(), threading.Event(), threading.Event()
    reviews = []

    class Client:
        def __init__(self, *args):
            pass

    class Monitor:
        def __init__(self, *args):
            pass

        def review(self, context, completion_pending=False):
            reviews.append(context)
            if len(reviews) == 1:
                return MonitorAction('wait', {'after_turns': 1})
            if len(reviews) == 2:
                current = self.completion_state()
                entered.set()
                assert release.wait(3)
                return MonitorAction('allow_complete', {'request_id': current['request_id']})
            resumed.set()
            return MonitorAction('wait', {'after_turns': 1})

    monkeypatch.setattr(provider, 'MonitorProviderClient', Client)
    monkeypatch.setattr(agent, 'MonitorAgent', Monitor)
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    runtime = MonitorRuntime(
        public_task='Complete the public task', task_workspace=workspace,
        artifact_dir=tmp_path / 'audit', config_name='fixture', model_config={},
        interrupt_callback=lambda message: None, process_factory=ThreadProcess,
    )
    outcomes = []
    waiter = threading.Thread(target=lambda: outcomes.append(
        runtime.request_completion({'internal_turn': 2})))
    try:
        # Wait for initialization, then let completion review retain a stale cursor
        # while ordinary boundary messages accumulate (the observed production race).
        deadline = time.monotonic() + 3
        while not reviews and time.monotonic() < deadline:
            time.sleep(.01)
        waiter.start()
        assert entered.wait(3)
        runtime.archive_boundary({'internal_turn': 3})
        runtime.archive_boundary({'internal_turn': 4})
        if stale:
            runtime._outputs.put({'kind': 'intervention', 'message': 'New correction',
                                  'request_id': 'correction', 'cursor': 3})
            waiter.join(3)
            assert outcomes and not outcomes[0].allow
        release.set()
        waiter.join(3)
        assert not waiter.is_alive()
        if stale:
            assert resumed.wait(3), 'Rejected approval must resume ordinary observation'
        else:
            assert outcomes[0].allow
            assert not resumed.wait(.4), 'Accepted approval must not consume queued patrol'
            assert runtime._process.is_alive(), 'Stay alive until normal owner close'
        assert runtime._pump.is_alive()
    finally:
        release.set()
        runtime.close()
        if waiter.ident is not None:
            waiter.join(3)
    assert not runtime._process.is_alive()
