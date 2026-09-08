import copy
import json
import multiprocessing as mp
import os

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.loop import run_review
from monitor_agent_core.provider import ModelResponse, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace


class Client:
    config = {}

    def __init__(self, crash=False):
        self.calls = []
        self.crash = crash

    def history_measure(self): return {}
    def export_history(self): return []
    def record_tool_results(self, results): pass

    def complete(self, messages, tools):
        self.calls.append(copy.deepcopy(messages))
        if len(self.calls) == 1:
            return ModelResponse('I will inspect the test assertion.', [
                ToolCall('read-1', 'file_read', json.dumps({'path': 'task/test.txt'}))], {})
        if self.crash:
            os._exit(0)  # Deliberately bypass MonitorAgent.review's finally.
        return ModelResponse('No discrepancy.', [ToolCall('wait-1', 'wait', '{"after_turns": 2}')], {})


def crash_worker(evidence, private):
    MonitorAgent(Client(crash=True), MonitorWorkspace(evidence, private)).review('Observe the task.')


def test_completed_tool_evidence_survives_process_exit_before_review_finishes(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    text = 'assert callback_count == 2\n' + 'long evidence\n' * 2000
    (evidence / 'test.txt').write_text(text, encoding='utf-8')
    private = tmp_path / 'private'
    proc = mp.get_context('spawn').Process(target=crash_worker, args=(evidence, private))
    proc.start()
    try:
        proc.join(8)
        assert proc.exitcode == 0
    finally:
        if proc.is_alive():
            proc.terminate()
            proc.join(2)
    rows = [json.loads(s) for s in (private / 'audit/dialogue.jsonl').read_text(encoding='utf-8').splitlines()]
    assert rows[0]['event'] == 'review_context'
    assert [x['event'] for x in rows][-1] == 'model_input'
    tool = next(x for x in rows if x['event'] == 'tool_result')
    assert 'assert callback_count == 2' in json.dumps(tool)
    assert any(x['event'] == 'tool_call' and 'task/test.txt' in x['arguments'] for x in rows)
    assert len({x['review_id'] for x in rows}) == 1
    assert not (private / 'audit/provider_history.json').exists()


def test_audit_changes_neither_model_messages_nor_action(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    (evidence / 'test.txt').write_text('assert 1 == 1')
    clients, actions = [], []
    for enabled in (False, True):
        client = Client()
        monitor = MonitorAgent(client, MonitorWorkspace(evidence, tmp_path / 'private'))
        records = []
        action = run_review(client, 'system', 'wake', [], monitor.dispatch,
                            audit=(lambda event, **kw: records.append((event, kw))) if enabled else None)
        clients.append(client)
        actions.append(action)
        if enabled:
            assert records[-1][0] == 'control_result'
    assert clients[0].calls == clients[1].calls
    assert actions[0] == actions[1]


def test_request_failure_is_distinguished_from_no_model_output(tmp_path):
    class Broken(Client):
        def complete(self, messages, tools): raise TimeoutError('fixture')
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    private = tmp_path / 'private'
    with pytest.raises(TimeoutError):
        MonitorAgent(Broken(), MonitorWorkspace(evidence, private)).review('wake')
    rows = [json.loads(s) for s in (private / 'audit/dialogue.jsonl').read_text().splitlines()]
    assert rows[-1]['event'] == 'model_error'
    assert rows[-1]['error_type'] == 'TimeoutError'
    assert not any(x['event'] == 'model_output' for x in rows)
