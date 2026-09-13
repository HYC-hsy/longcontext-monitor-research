import pytest

from monitor_agent_core.agent import MONITOR_TOOLS
from monitor_agent_core.workspace import MonitorWorkspace


@pytest.fixture
def ws(tmp_path):
    task = tmp_path / 'task'
    task.mkdir()
    return MonitorWorkspace(task, tmp_path / 'private')


def collect(ws, arguments):
    text, pages = '', []
    while arguments:
        arguments = dict(arguments)
        path = arguments.pop('path')
        result = ws.read_text(path, **arguments)
        assert len(result['content']) <= arguments.get('max_chars', 20000)
        text += result['content']
        pages.append(result)
        arguments = result['next_read']
        assert len(pages) < 100
    return text, pages


def test_tail_always_in_base_schema():
    tool = next(t['function'] for t in MONITOR_TOOLS if t['function']['name'] == 'file_read')
    assert tool['parameters']['required'] == ['path']
    assert 'tail' in tool['parameters']['properties']


def test_long_unicode_line_lossless(ws):
    text = '起点🙂' * 12000 + '\nlast\n'
    (ws.evidence_root / 'events.jsonl').write_text(text, encoding='utf-8')
    actual, pages = collect(ws, {'path': 'task/events.jsonl', 'max_chars': 5000})
    assert actual == text
    assert pages[0]['truncated']
    assert pages[0]['next_read']['offset'] == 5000
    assert not pages[-1]['truncated']


@pytest.mark.parametrize('budget', [1, 3, 4, 7, 100])
def test_requested_range_only_and_newline_boundaries(ws, budget):
    (ws.evidence_root / 'x').write_bytes(b'zero\r\none\r\ntwo\r\nthree\r\n')
    actual, pages = collect(ws, {'path': 'task/x', 'start': 2, 'count': 2, 'max_chars': budget})
    assert actual == 'one\ntwo\n'
    assert pages[-1]['more_lines_after_range']


def test_tail_continuation_does_not_repeat_tail(ws):
    (ws.evidence_root / 'x').write_text('first\nsecond\nlast', encoding='utf-8')
    actual, pages = collect(ws, {'path': 'task/x', 'tail': True, 'count': 2, 'max_chars': 3})
    assert actual == 'second\nlast'
    assert pages[0]['start'] == 2
    assert 'tail' not in pages[0]['next_read']


def test_empty_and_beyond_eof(ws):
    (ws.evidence_root / 'x').write_text('', encoding='utf-8')
    assert ws.read_text('task/x')['next_read'] is None
    assert ws.read_text('task/x', start=9)['content'] == ''


def test_missing_file_explains_absence(ws):
    with pytest.raises(FileNotFoundError, match='may not have been created yet'):
        ws.read_text('task/synopsis.jsonl')


def test_invalid_offsets_and_budget(ws):
    (ws.evidence_root / 'x').write_text('ab', encoding='utf-8')
    for kwargs in [{'offset': 3}, {'offset': -1}, {'offset': 1, 'tail': True}, {'max_chars': 0}]:
        with pytest.raises(ValueError):
            ws.read_text('task/x', **kwargs)
