"""No-model publication, Task visibility, and reminder delivery tests."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys

import pytest

from memory_agent.memory.universal_memory import UniversalMemory
from task_knowledge_file import TaskKnowledgeFile, KnowledgePublicationError, TASK_MEMORY_PATH, TASK_MEMORY_NOTICE
from test_remind_first_loop import read, add, done
from test_reminder_tool_loop import remind as decision
from test_predictive_tool_recovery import block_network  # noqa: F401


def create(tmp_path, run='run', task='task'):
    directory = tmp_path / run / 'responses'
    directory.mkdir(parents=True)
    bank = UniversalMemory()
    return bank, TaskKnowledgeFile(bank, directory, run_id=run, task_id=task)


def content(file):
    return json.loads(file.path.read_text(encoding='utf-8'))


def test_empty_then_incremental_exact_order_and_idempotence(tmp_path):
    bank, file = create(tmp_path)
    assert content(file) == {'run_id': 'run', 'task_id': 'task', 'knowledge': []}
    values = ['中文\n```python\nx = "\\n"\n```', '<tag> & 😀', 'same', 'same']
    ids = [bank.save_knowledge(value) for value in values]
    assert [x['content'] for x in content(file)['knowledge']] == values
    assert [x['id'] for x in content(file)['knowledge']] == ids
    before = file.path.stat().st_mtime_ns
    file.publish()
    assert file.path.stat().st_mtime_ns == before
    assert len(content(file)['knowledge']) == 4  # Intentional repeated model writes stay unchanged.
    assert not list(file.path.parent.glob('.memory-*'))
    assert file.path.stat().st_mode & 0o444 == 0o444
    assert file.path.parent.stat().st_mode & 0o111 == 0o111


def test_isolation_and_only_knowledge_exposed(tmp_path):
    a, fa = create(tmp_path, 'a', 'task-a')
    b, fb = create(tmp_path, 'b', 'task-b')
    a.status = 'private-status'
    a.save_procedural('private-procedure')
    a.save_knowledge('A')
    b.save_knowledge('B')
    assert content(fa)['task_id'] == 'task-a'
    assert [x['content'] for x in content(fb)['knowledge']] == ['B']
    assert 'private' not in fa.path.read_text()


def test_existing_file_and_nonempty_bank_rejected(tmp_path):
    bank, file = create(tmp_path)
    with pytest.raises(KnowledgePublicationError):
        TaskKnowledgeFile(bank, file.path.parent.parent, run_id='other', task_id='other')
    bank.save_knowledge('existing')
    directory = tmp_path / 'fresh'; directory.mkdir()
    with pytest.raises(KnowledgePublicationError):
        TaskKnowledgeFile(bank, directory, run_id='r', task_id='t')


def test_failed_original_add_does_not_publish(tmp_path):
    directory = tmp_path / 'responses'; directory.mkdir()
    bank = UniversalMemory()
    def rejected(_):
        raise ValueError('not saved')
    bank.save_knowledge = rejected
    file = TaskKnowledgeFile(bank, directory, run_id='r', task_id='t')
    with pytest.raises(ValueError): bank.save_knowledge('bad')
    assert content(file)['knowledge'] == []


def test_failed_publish_is_fatal_not_success_or_duplicate_retry(tmp_path, monkeypatch):
    bank, file = create(tmp_path)
    def fail(*_): raise OSError('disk error')
    monkeypatch.setattr('task_knowledge_file.os.replace', fail)
    with pytest.raises(KnowledgePublicationError): bank.save_knowledge('accepted on host')
    assert len(bank.knowledge) == 1
    assert content(file)['knowledge'] == []  # Atomic old version, never a partial JSON.
    with pytest.raises(KnowledgePublicationError): bank.save_knowledge('do not retry')
    assert len(bank.knowledge) == 1
    assert not list(file.path.parent.glob('.memory-*'))


@pytest.mark.parametrize('reminder', [None, '', '   '])
def test_silent_has_no_extra_input(tmp_path, reminder):
    _, file = create(tmp_path)
    assert file.append_notice(reminder) == reminder


def test_notice_preserves_original_and_fixed_task_path(tmp_path):
    _, file = create(tmp_path)
    original = '条件\n```python\nx = 3\n```\n'
    delivered = file.append_notice(original)
    assert delivered == original + TASK_MEMORY_NOTICE
    assert delivered.count(TASK_MEMORY_NOTICE) == 1
    assert TASK_MEMORY_PATH == '/run/pma-bridge/responses/knowledge/memory.json'
    assert TASK_MEMORY_NOTICE == (
        '\n\nAfter receiving this reminder, you must open the knowledge bank at '
        '/run/pma-bridge/responses/knowledge/memory.json and cross-check the reminder against '
        "the relevant entries before acting, so you don't miss important information and can "
        'recover any additional context needed for your judgment.')


def test_existing_mount_maps_file_and_separate_process_can_read(tmp_path):
    # Simulate the host->Task mount mapping; not a live Docker verification.
    bank, file = create(tmp_path)
    bank.save_knowledge('原文')
    mounts = {'/run/pma-bridge/responses': file.path.parent.parent}
    mapped = mounts['/run/pma-bridge/responses'] / Path(TASK_MEMORY_PATH).relative_to('/run/pma-bridge/responses')
    output = subprocess.check_output([sys.executable, '-c',
        'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))["knowledge"][0]["content"])',
        str(mapped)], text=True)
    assert output.strip() == '原文'
    stage = Path(__file__).resolve().parents[1] / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
    source = (stage / 'offline_launcher.py').read_text()
    assert '"target": "/run/pma-bridge/responses", "read_only": True' in source


def test_actual_episode_saves_before_delivery_and_preserves_frozen_reminder(tmp_path):
    from episode import PMAEpisode, construct_upstream
    host = construct_upstream(tmp_path / 'agent', research_candidate='pma_predictive_read_context_v1',
                              memory_api_key='synthetic', memory_api_base='https://example.invalid')
    episode = PMAEpisode(host, run_id='r', task_id='t', archive=tmp_path / 'archive')
    directory = tmp_path / 'responses'; directory.mkdir()
    file = TaskKnowledgeFile(host._memory, directory, run_id='r', task_id='t')
    episode.task_knowledge_file = file
    snapshots = []
    replies = iter([read(), decision('Original reminder.\n```python\nx=1\n```'), add('newly saved'), done()])
    async def call(**kwargs):
        snapshots.append((host._pending_injection, content(file)))
        return next(replies)
    host._memory_llm.call = call
    async def execute():
        start = {'run_id':'r','task_id':'t','event_id':'start','sequence':1,'kind':'task_start',
                 'initial_user_content':'Original task'}
        first = await episode.handle(start)
        assert await episode.handle(start) == first  # Replay doesn't duplicate writes.
        result = await episode.handle({'run_id':'r','task_id':'t','event_id':'before','sequence':2,
                                      'kind':'before_actor_call','actor_attempt':1})
        return result
    result = asyncio.run(execute())
    assert all(pending is None for pending, _ in snapshots)
    assert snapshots[2][1]['knowledge'] == []  # Before add execution.
    assert snapshots[3][1]['knowledge'][0]['content'] == 'newly saved'
    assert len(content(file)['knowledge']) == 1
    assert 'Original reminder.\n```python\nx=1\n```' in result['reminder']
    assert result['reminder'].endswith(TASK_MEMORY_NOTICE)
    assert 'newly saved' not in result['reminder']
    # Finalization still writes original private artifacts without overwriting public projection.
    episode.finalize_without_event('test')
    private = json.loads((episode.archive / 'memory.json').read_text())
    assert private['knowledge'] == content(file)['knowledge']
    assert (episode.archive / 'task_visible_memory.json').read_bytes() == file.path.read_bytes()


def test_worker_installs_projection_only_for_current_candidate_before_ready():
    stage = Path(__file__).resolve().parents[1] / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
    source = (stage / 'worker_main.py').read_text()
    start = source.index("    if args.research_candidate == 'pma_predictive_read_context_v1':\n        from task_knowledge_file")
    assert start < source.index('    install_transport_audit(agent, episode.archive)')
    assert start < source.index('(private / "worker_ready.json")')


def test_publication_failure_returns_error_receipt_and_finalizes_host_bank(tmp_path, monkeypatch):
    from episode import PMAEpisode, construct_upstream
    from event_spool import EventDispatcher
    host = construct_upstream(tmp_path / 'agent', research_candidate='pma_predictive_read_context_v1',
                              memory_api_key='synthetic', memory_api_base='https://example.invalid')
    episode = PMAEpisode(host, run_id='r', task_id='t', archive=tmp_path / 'archive')
    requests, responses = tmp_path/'spool/requests', tmp_path/'spool/responses'
    requests.mkdir(parents=True); responses.mkdir()
    file = TaskKnowledgeFile(host._memory, responses, run_id='r', task_id='t')
    episode.task_knowledge_file = file
    replies = iter([read(), decision('Not delivered.'), add('host-only-on-failure'), done()])
    async def call(**kwargs): return next(replies)
    host._memory_llm.call = call
    request = {'schema':'pma-ga-events-v1','run_id':'r','task_id':'t','event_id':'start',
               'sequence':1,'kind':'task_start','initial_user_content':'Original task'}
    (requests/'start.json').write_text(json.dumps(request))
    original = __import__('os').replace
    def fail_snapshot(src, dst):
        if Path(dst).name == 'memory.json': raise OSError('synthetic sync failure')
        return original(src, dst)
    monkeypatch.setattr('task_knowledge_file.os.replace', fail_snapshot)
    dispatcher = EventDispatcher(episode, requests, responses)
    with pytest.raises(KnowledgePublicationError): asyncio.run(dispatcher.serve_once())
    receipt = json.loads((responses/'start.json').read_text())
    assert receipt['status'] == 'error'
    assert receipt['error_type'] == 'KnowledgePublicationError'
    assert host._get_memory_system_prompt() is None
    assert content(file)['knowledge'] == []
    episode.finalize_without_event('publication_failed')
    assert json.loads((episode.archive/'memory.json').read_text())['knowledge'][0]['content'] == 'host-only-on-failure'
    assert json.loads((episode.archive/'task_visible_memory.json').read_text())['knowledge'] == []


def test_private_host_umask_does_not_block_task_reader(tmp_path):
    import os
    previous = os.umask(0o077)
    try:
        bank, file = create(tmp_path)
        bank.save_knowledge('Readable by Task UID')
    finally:
        os.umask(previous)
    assert file.path.parent.stat().st_mode & 0o777 == 0o755
    assert file.path.stat().st_mode & 0o777 == 0o644
