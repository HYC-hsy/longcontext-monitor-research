import asyncio
import sys
from types import SimpleNamespace

import pytest

from test_harbor_ga_lhtb import load_adapter


def test_outer_cancellation_keeps_partial_identity_and_installs_live_archive(monkeypatch):
    load_adapter(monkeypatch)
    cls = sys.modules['adapters.harbor_ga_agent'].M4GenericAgent
    agent = cls(model_name='test', llm_no=0, run_id='audit-run', expected_model='test',
                python_home='python-home', ga_source_sha256='abc', timeout_sec=60,
                task_id='test:task')
    calls = []
    context = SimpleNamespace(metadata=None)

    class Environment:
        async def exec(self, command, **kwargs):
            calls.append(command)
            if 'for i in $(seq' in command:
                assert context.metadata['run_id'] == 'audit-run'
                assert context.metadata['archive_status'] == 'running_partial'
                assert context.metadata['wrapper_return_code'] is None
                assert 'trap archive_output EXIT' in command
                assert command.index('  archive_output\n') < command.index('  sleep 2')
                raise asyncio.CancelledError()
            return SimpleNamespace(return_code=0, stdout='', stderr='')

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(agent.run('public task', Environment(), context))
    assert context.metadata['round_end_seen'] is False
    assert any('m4_agent_identity.json' in c for c in calls[:-1])
