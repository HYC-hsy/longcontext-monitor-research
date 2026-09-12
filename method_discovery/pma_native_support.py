"""Transport configuration and observational metering, not a PMA policy fork."""
import json
from pathlib import Path
import time
from urllib.parse import urlsplit


def original_config(reference, *, port=18765):
    from memory_agent.config import load_config
    config = load_config(Path(reference) / 'configs/memory_terminalbench.yaml')
    # Same model families/releases; CC-VIBE uses Anthropic rather than OpenRouter.
    # The provider prefix is LiteLLM routing metadata, not a replacement model.
    config.model.model_name = 'anthropic/claude-sonnet-4-5-20250929'
    config.memory.model_name = 'anthropic/claude-opus-4-6'
    for side in (config.model, config.memory):
        side.api_base = f'http://127.0.0.1:{port}'
        side.api_key = 'isolated-local-channel'
    config.run.n_parallel = 1
    return config


def gateway_config(base, key):
    endpoint = urlsplit(base)
    if (endpoint.scheme != 'https' or not endpoint.hostname or endpoint.username
            or endpoint.password or endpoint.query or endpoint.fragment):
        raise ValueError('A fixed HTTPS inference endpoint is required')
    if not key:
        raise ValueError('Gateway credential is required')
    headers = ({'x-api-key': key} if key.startswith('sk-ant-') else
               {'Authorization': 'Bearer ' + key})
    return {'models': {name: {'base': base.rstrip('/'), 'headers': headers,
                             'paths': ['/v1/messages']} for name in
                       ('claude-sonnet-4-5-20250929', 'claude-opus-4-6')}}


def attach_usage(agent, output):
    """Record each logical call; preserve exact objects, exceptions and arguments.

    Retry attempts inside the author's client remain included in latency, but
    unreturned usage cannot be recovered and must not be represented as zero.
    """
    path = Path(output) / 'model_calls.jsonl'
    for actor, attr in (('task', '_llm'), ('memory', '_memory_llm')):
        client = getattr(agent, attr, None)
        if client is None:
            continue
        original = client.call

        async def measured(*args, _call=original, _actor=actor, **kwargs):
            started = time.time()
            clock = time.monotonic()
            row = {'actor': _actor, 'started_unix': started, 'usage': None,
                   'status': 'cancelled', 'unit': 'logical_client_call',
                   'retry_attempt_usage_complete': False}
            try:
                result = await _call(*args, **kwargs)
                usage = getattr(result, 'usage', None)
                if usage is not None:
                    row['usage'] = usage.model_dump(mode='json')
                row['status'] = 'returned'
                return result
            except Exception as exc:
                row.update(status='failed', error_type=type(exc).__name__)
                raise
            finally:
                row['elapsed_seconds'] = time.monotonic() - clock
                with path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(row) + '\n')
        client.call = measured
