from dataclasses import replace
import pytest

from test_monitor_pma_memory import Client, comparison, response, workspace
from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.task_understanding import TaskUnderstanding


def client_for(responses):
    client = Client(responses)
    client.config = {**client.config, 'monitor_task_model': True}
    return client


def initial():
    result = response('memory_save_knowledge', content='Both forms are required.')
    return replace(result, content='<task_model>Both short and long forms must behave correctly; inspect both paths.</task_model>')


def test_initial_model_reuses_two_calls_and_reaches_phase2_and_main(workspace):
    client = client_for([initial(), comparison(), response('wait', after_turns=1)])
    monitor = MonitorAgent(client, workspace)
    assert monitor.review('Initialize').kind == 'wait'
    assert len(client.inputs) == 3
    assert 'Support both short and long forms.' in str(client.inputs[0])
    assert 'Both short and long forms must behave correctly' in str(client.inputs[1])
    assert 'Both short and long forms must behave correctly' in client.inputs[2][2]
    saved = (workspace.private_root / 'task_model.md').read_text()
    assert 'task/original_task.txt' in saved
    assert client.history[0]['content'] == 'Previous investigation remains available.'


@pytest.mark.parametrize('bad', ['', '<task_model></task_model>', '<task_model>A</task_model><task_model>B</task_model>'])
def test_missing_initial_model_fails_explicitly_without_committing(workspace, bad):
    result = replace(initial(), content=bad)
    client = client_for([result])
    monitor = MonitorAgent(client, workspace)
    with pytest.raises(RuntimeError, match='task_model'):
        monitor.review('Initialize')
    assert not (workspace.private_root / 'task_model.md').exists()
    assert not (workspace.private_root / 'pma_memory.json').exists()


def test_phase2_failure_discards_draft(workspace):
    client = client_for([initial(), RuntimeError('fixture outage')])
    monitor = MonitorAgent(client, workspace)
    with pytest.raises(RuntimeError):
        monitor.review('Initialize')
    assert monitor.task_understanding.draft is None
    assert not (workspace.private_root / 'task_model.md').exists()


def test_local_status_cannot_overwrite_task_model_and_explicit_revision_is_used(workspace):
    workspace.write_text('monitor/task_model.md', 'Both behaviors remain required.')
    client = client_for([response('memory_update_status', content='One repair done.'), comparison(),
                         response('wait', after_turns=1)])
    monitor = MonitorAgent(client, workspace)
    monitor.review('Continue')
    assert (workspace.private_root / 'task_model.md').read_text() == 'Both behaviors remain required.'
    workspace.write_text('monitor/task_model.md', 'Revised understanding from the original task.')
    assert 'Revised understanding' in monitor._active_working_context()


def test_new_completion_in_same_review_gets_full_original_once(workspace):
    workspace.write_text('monitor/task_model.md', 'Local repair is not the whole task.')
    monitor = MonitorAgent(client_for([]), workspace)
    monitor.completion_state = lambda: {'generation': 1, 'cursor': 19}
    text = monitor._refresh_completion()
    assert 'Support both short and long forms.' in text
    assert 'Local repair is not the whole task.' in text
    assert monitor._refresh_completion() is None
    monitor.completion_state = lambda: {'generation': 2, 'cursor': 25}
    assert 'Full original task' in monitor._refresh_completion()


def test_existing_completion_without_callback_and_disabled_candidate(workspace):
    workspace.write_text('monitor/task_model.md', 'Behavior standard')
    client = client_for([response('memory_update_status', content='Repair done'), comparison(),
                         response('allow_complete')])
    assert MonitorAgent(client, workspace).review('Finish', completion_pending=True).kind == 'allow_complete'
    assert 'Full original task' in str(client.inputs[2])
    plain = Client([])
    assert MonitorAgent(plain, workspace).task_understanding is None


def test_other_task_does_not_inherit_interpretation(tmp_path, workspace):
    from monitor_agent_core.workspace import MonitorWorkspace
    workspace.write_text('monitor/task_model.md', 'First task')
    other = tmp_path / 'other'
    other.mkdir()
    assert TaskUnderstanding(MonitorWorkspace(other, tmp_path / 'private-other')).read() == ''
