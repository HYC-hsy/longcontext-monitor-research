"""Three bounded real API checks through the native isolated inference path."""
import asyncio
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

from harbor.llms.lite_llm import LiteLLM
from pma_native_support import original_config

REFERENCE = Path('/workspace/some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent')


async def probe(output):
    config = original_config(REFERENCE)
    rows = []
    for kind, side in [('task_text', config.model), ('memory_tool', config.memory),
                       ('memory_text', config.memory)]:
        llm = LiteLLM(model_name=side.model_name, api_base=side.api_base,
                      api_key=side.api_key, temperature=side.temperature)
        kwargs = {'prompt': 'Reply with Hello in one short sentence.', 'max_tokens': 128}
        if kind == 'memory_tool':
            kwargs = {'prompt': 'Call record_fact with text equal to Hello. Do not answer in prose.',
                      'max_tokens': 256, 'tools': [{'type': 'function', 'function': {
                          'name': 'record_fact', 'description': 'Record a short fact.',
                          'parameters': {'type': 'object', 'properties': {'text': {'type': 'string'}},
                                         'required': ['text']}}}]}
        started = time.monotonic()
        row = {'check': kind, 'requested_model': side.model_name}
        try:
            result = await asyncio.wait_for(llm.call(**kwargs), timeout=120)
            calls = getattr(result, 'tool_calls', None) or []
            valid = bool(result.content.strip()) if kind != 'memory_tool' else any(
                call.function.name == 'record_fact' and
                json.loads(call.function.arguments).get('text') == 'Hello' for call in calls)
            row.update(status='passed' if valid else 'unexpected_response',
                       text=result.content[:160], tool_names=[c.function.name for c in calls],
                       usage=result.usage.model_dump(mode='json') if result.usage else None)
        except Exception as exc:
            row.update(status='failed', error_type=type(exc).__name__)
        row['elapsed_seconds'] = time.monotonic() - started
        rows.append(row)
        output.write_text(json.dumps({'real_task_started': False, 'checks': rows}, indent=2), encoding='utf-8')
        print(json.dumps(row), flush=True)
    return rows


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    bridge = subprocess.Popen([sys.executable, str(Path(__file__).with_name('isolated_transport.py')), 'local'])
    try:
        for _ in range(100):
            if bridge.poll() is not None:
                raise RuntimeError('Bridge exited')
            try:
                with socket.create_connection(('127.0.0.1', 18765), timeout=.1):
                    break
            except OSError:
                time.sleep(.1)
        else:
            raise TimeoutError('Bridge readiness')
        rows = asyncio.run(probe(output))
        if not all(row['status'] == 'passed' for row in rows):
            sys.exit(1)
    finally:
        bridge.terminate()
        bridge.wait(timeout=10)
