import json
import pytest
from monitor_agent_core.configuration import load_profile
from monitor_agent_core.provider import MonitorProviderClient, RetryableProviderError


def test_private_profile_does_not_need_task_config(tmp_path):
    path = tmp_path / 'models.local.json'
    profile = dict(provider='anthropic', model='claude-test', apibase='https://example.invalid', apikey='TEST')
    path.write_text(json.dumps({'monitor': profile}))
    assert load_profile('monitor', path) == profile
    with pytest.raises(ValueError):
        load_profile('missing', path)


def test_claude_roundtrip_retains_signed_blocks(monkeypatch):
    c = MonitorProviderClient('monitor', dict(provider='anthropic', model='claude-test',
        apibase='https://example.invalid', apikey='TEST', reasoning_effort='high'))
    blocks = [dict(type='thinking', thinking='inspect', signature='signed'),
              dict(type='redacted_thinking', data='opaque'),
              dict(type='tool_use', id='t1', name='file_read', input={'path': 'task/x'})]
    monkeypatch.setattr(c, '_request', lambda tools: (blocks, {}))
    c.complete([dict(role='user', content='Inspect')], [])
    monkeypatch.setattr(c, '_request', lambda tools: ([dict(type='text', text='done')], {}))
    c.complete([dict(role='user', tool_results=[dict(tool_use_id='t1', content='evidence')])], [])
    url, headers, payload = c._anthropic_request([])
    assert url.endswith('/v1/messages?beta=true')
    assert payload['thinking'] == {'type': 'adaptive'}
    assert payload['messages'][1]['content'] == blocks
    assert payload['messages'][2]['content'][0]['tool_use_id'] == 't1'


def test_claude_redacted_and_truncated_stream():
    c = MonitorProviderClient('monitor', dict(provider='anthropic', model='claude-test',
        apibase='https://example.invalid', apikey='TEST'))
    events = [dict(type='content_block_start', content_block=dict(type='redacted_thinking', data='opaque')),
              dict(type='content_block_stop')]
    lines = ['data: ' + json.dumps(e) for e in events]
    with pytest.raises(RetryableProviderError):
        c._parse_anthropic(lines)
    blocks, _ = c._parse_anthropic(lines + ['data: {"type":"message_stop"}'])
    assert blocks == [dict(type='redacted_thinking', data='opaque')]
