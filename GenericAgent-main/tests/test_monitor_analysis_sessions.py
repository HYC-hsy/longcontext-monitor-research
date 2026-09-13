import os
from pathlib import Path
import threading
import time

import pytest

from monitor_agent_core.process_runner import AnalysisSessions


@pytest.fixture
def sessions(tmp_path):
    runner = AnalysisSessions(tmp_path, threading.Event())
    yield runner
    runner.close()


def drain(sessions, first):
    text = first['stdout']
    current = first
    for _ in range(30):
        if current['next_read'] is None:
            return text, current
        current = sessions.read(**current['next_read'])
        text += current['stdout']
    raise AssertionError('Did not settle')


def test_short_command_and_full_archive(sessions):
    result = sessions.start("print('hello')")
    assert result['status'] == 'success'
    assert result['stdout'].strip() == 'hello'
    path = sessions.cwd / result['output_path'].removeprefix('monitor/')
    assert path.read_text().strip() == 'hello'


def test_incremental_output_before_exit(sessions):
    result = sessions.start("import time\nprint('first', flush=True)\ntime.sleep(1)\nprint('second')",
                            wait_seconds=0.3)
    assert result['status'] == 'running'
    assert 'first' in result['stdout']
    text, final = drain(sessions, result)
    assert text == 'first\nsecond\n' or text == 'first\r\nsecond\r\n'
    assert final['exit_code'] == 0


def test_large_unicode_output_lossless(sessions):
    result = sessions.start("print('🙂中' * 10000, end='')")
    text, final = drain(sessions, result)
    assert text == '🙂中' * 10000
    assert final['unread_bytes'] == 0


@pytest.mark.parametrize('how', ['cancel', 'timeout', 'close'])
def test_cleanup(sessions, how):
    result = sessions.start('import time\ntime.sleep(30)', timeout=0.2 if how == 'timeout' else 60,
                            wait_seconds=0)
    if how == 'cancel':
        result = sessions.read(result['session_id'], cancel=True)
    elif how == 'close':
        sessions.stop_event.set()
    _, final = drain(sessions, result)
    assert final['status'] == 'error'
    assert final['reason'] == ('timeout' if how == 'timeout' else 'cancelled')
    assert sessions.sessions[result['session_id']]['process'].poll() is not None


def test_unknown_session_and_ambiguous_input(sessions):
    with pytest.raises(ValueError, match='Unknown session'):
        sessions.read('another-task')
    with pytest.raises(ValueError):
        sessions.start('print(1)', wait_seconds=6)


@pytest.mark.skipif(os.name == 'nt', reason='Linux task runtime process groups')
def test_shell_child_is_killed_on_cancel(sessions):
    result = sessions.start('sleep 30 &\necho $!\nwait', 'bash', wait_seconds=0.2)
    child = int(result['stdout'].strip())
    _, final = drain(sessions, sessions.read(result['session_id'], cancel=True))
    assert final['reason'] == 'cancelled'
    stat = Path(f'/proc/{child}/stat')
    assert not stat.exists() or stat.read_text().split()[2] == 'Z'
