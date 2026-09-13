import queue
import subprocess
import sys
import threading

from monitor_agent_core.actions import MonitorAction
from monitor_agent_core.runtime import _worker


def test_follow_wakes_do_not_cancel_running_tool_then_patrol_stops(tmp_path, monkeypatch):
    class Client:
        def __init__(self, *args): pass
    reviews = []
    class Monitor:
        def __init__(self, *args, **kwargs): pass
        def review(self, *args, **kwargs):
            reviews.append(True)
            return MonitorAction('wait', {'after_turns': 1,
                'mode': 'patrol' if len(reviews) == 4 else 'follow'})
    monkeypatch.setattr('monitor_agent_core.provider.MonitorProviderClient', Client)
    monkeypatch.setattr('monitor_agent_core.agent.MonitorAgent', Monitor)
    commands, outputs, receipts = queue.Queue(), queue.Queue(), queue.Queue()
    stop = threading.Event()
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    config = dict(config_name='fixture', model_config={}, evidence_root=evidence,
        private_root=tmp_path / 'private', task_workspace=tmp_path,
        max_review_turns=20, wake_receipts=receipts, stop_event=stop)
    worker = threading.Thread(target=_worker, args=(config, commands, outputs))
    worker.start()
    process = None
    try:
        initial = outputs.get(timeout=3)
        assert initial['kind'] == 'review_wake'
        receipts.put(dict(identity=initial['identity'], accepted=True))
        assert outputs.get(timeout=3)['mode'] == 'follow'
        assert outputs.get(timeout=3)['kind'] == 'ready'
        process = subprocess.Popen([sys.executable, '-c',
            'import sys; sys.stdin.readline(); print("check completed")'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        # Simulate host cancellation while a real tool process is running.
        for turn in (1, 2, 3):
            commands.put(dict(kind='boundary', task_turn=turn, cursor=turn * 2 - 1))
            event = outputs.get(timeout=3)
            if event['kind'] == 'review_wake':
                process.terminate()
            assert event['kind'] == 'review_silent'
            assert process.poll() is None
        assert event['mode'] == 'patrol'
        stdout, _ = process.communicate('\n', timeout=3)
        assert stdout.strip() == 'check completed' and process.returncode == 0
        commands.put(dict(kind='boundary', task_turn=4, cursor=7))
        assert outputs.get(timeout=3)['kind'] == 'review_wake'
    finally:
        stop.set()
        commands.put(dict(kind='close'))
        worker.join(3)
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate()
    assert not worker.is_alive()
