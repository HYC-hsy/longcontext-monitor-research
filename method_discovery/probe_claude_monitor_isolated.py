"""Independent monitor tool roundtrip through the production isolated transport."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

PROFILE = 'claude_monitor_opus48'


def worker():
    from monitor_agent_core.configuration import load_profile
    from monitor_agent_core.provider import MonitorProviderClient
    cfg = load_profile(PROFILE)
    cfg.update(max_retries=0, read_timeout=180)
    client = MonitorProviderClient(PROFILE, cfg)
    tool = {'type': 'function', 'function': {'name': 'read_sample',
        'description': 'Read the sample value for this connectivity test.',
        'parameters': {'type': 'object', 'properties': {'label': {'type': 'string'}},
                       'required': ['label'], 'additionalProperties': False}}}
    result = {'model': client.model, 'provider': client.provider, 'task_started': False}
    start = time.monotonic()
    try:
        first = client.complete([{'role': 'user', 'content':
            'Call read_sample once with label="connection-check", then return its value without other text.'}], [tool])
        result['first_seconds'] = round(time.monotonic() - start, 3)
        result['tool_calls'] = [{'name': c.name, 'arguments': c.arguments} for c in first.tool_calls]
        result['first_text'] = first.content[:500]
        assert len(first.tool_calls) == 1 and first.tool_calls[0].name == 'read_sample'
        assert json.loads(first.tool_calls[0].arguments) == {'label': 'connection-check'}
        value = 'sample-' + uuid.uuid4().hex[:10]
        second = client.complete([{'role': 'user', 'tool_results': [
            {'tool_use_id': first.tool_calls[0].id, 'content': value}]}], [tool])
        result['passed'] = second.content.strip() == value and not second.tool_calls
        result['usage'] = client.usage_records
    except Exception as exc:
        result.update(passed=False, error_type=type(exc).__name__,
                      error=str(exc).replace(cfg['apikey'], '[REDACTED]')[:400])
    result['seconds'] = round(time.monotonic() - start, 3)
    print(json.dumps(result), flush=True)
    return 0 if result.get('passed') else 1


def probe(output):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'long_context_bench'))
    from scripts.isolated_run_bundle import build_bundle
    runtime = root / 'bench_runtime/m2/linux'
    home = next((runtime / 'python').glob('cpython-3.12.*-linux-x86_64-gnu')).name
    source, compose_path = build_bundle(output, root / 'GenericAgent-main', runtime,
        home, 'native_claude_cc_vibe_opus48', PROFILE, 15340,
        monitor_profile_path=root / 'monitor_config/models.local.json')
    shutil.copy2(__file__, source / 'probe_monitor.py')
    compose = json.loads(compose_path.read_text())
    main = compose['services']['main']
    main.update(image='znpt/roadmapbench-fyn-2.2.0-roadmap', command=['sleep', 'infinity'])
    main['volumes'] += [f'{runtime.as_posix()}:/opt/m4-runtime:ro', f'{source.as_posix()}:/source:ro']
    main['environment'] = {'PYTHONPATH': '/source:/opt/m4-runtime/ga-env/lib/python3.12/site-packages'}
    compose_path.write_text(json.dumps(compose))
    prefix = ['docker', 'compose', '-p', 'monitor-probe-' + uuid.uuid4().hex[:8], '-f', str(compose_path)]
    python = f'/opt/m4-runtime/python/{home}/bin/python3.12'
    try:
        subprocess.run(prefix + ['up', '-d', '--wait'], check=True, timeout=120, capture_output=True)
        subprocess.run(prefix + ['exec', '-d', 'main', python, '/source/isolated_transport.py', 'local'], check=True)
        result = subprocess.run(prefix + ['exec', '-T', 'main', python, '/source/probe_monitor.py', '--worker'],
            capture_output=True, text=True, encoding='utf-8', timeout=420)
        (Path(output) / 'probe_result.jsonl').write_text(result.stdout, encoding='utf-8')
        print(result.stdout, flush=True)
        if result.returncode:
            raise RuntimeError('Independent Claude monitor probe failed; inspect probe_result.jsonl')
    finally:
        subprocess.run(prefix + ['down', '--volumes', '--remove-orphans'], check=True, timeout=60, capture_output=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.worker:
        raise SystemExit(worker())
    if not args.output:
        parser.error('--output is required')
    probe(args.output)
