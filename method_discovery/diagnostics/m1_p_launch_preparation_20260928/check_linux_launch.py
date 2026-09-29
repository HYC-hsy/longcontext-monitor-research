"""Fixed no-model Linux launch check. Never starts Task agentmain or verifier."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from prepare_bundle import prepare, ROOT, HERE, blob, POLICY_COMMIT, POLICY_PATH, sha

PYHOME = 'cpython-3.12.12-linux-x86_64-gnu'
PYTHON = '/opt/m4-runtime/python/' + PYHOME + '/bin/python3.12'
RUNTIME = ROOT / 'bench_runtime/m2/linux'
IMAGES = {'kitex': 'sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e',
          'ratatui': 'sha256:6f9da0a2c21293e8e0d2bac70947260da9edd9e3de0bcb09af3008218bbcc18d'}
GATEWAY_IMAGE = 'sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171'


def command(args, timeout=180):
    r = subprocess.run(args, capture_output=True, timeout=timeout)
    return {'command': args, 'returncode': r.returncode,
            'stdout': r.stdout.decode('utf-8', 'replace'), 'stderr': r.stderr.decode('utf-8', 'replace')}


def normalized(payload, capture):
    # Exact recorded analysis-session identities only; retain all task/history.
    result = copy.deepcopy(payload)
    sessions = []
    for response in capture['scripted_responses']:
        if response.get('name') == 'code_run':
            tool_id = response['id']
            for message in result.get('messages', []):
                for block in message.get('content', []) if isinstance(message.get('content'), list) else []:
                    if block.get('type') == 'tool_result' and block.get('tool_use_id') == tool_id:
                        data = json.loads(block['content'])
                        sessions.append((data['session_id'], tool_id))
    def visit(value):
        if isinstance(value, str):
            for ident, label in sessions: value = value.replace(ident, '<' + label + '-session>')
            return value
        if isinstance(value, list): return [visit(v) for v in value]
        if isinstance(value, dict): return {k: visit(v) for k, v in value.items()}
        return value
    return visit(result), sessions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--supervisor-source', required=True)
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args()
    out = Path(args.output_root).resolve()
    out.mkdir(parents=True, exist_ok=False)
    summary = {'engineering_only': True, 'actual_model_requests': 0, 'records': [], 'comparisons': []}
    body = blob(POLICY_COMMIT, POLICY_PATH).decode().strip()
    for case, image in IMAGES.items():
        captures = []
        for enabled in (False, True):
            name = case + ('_p' if enabled else '_m1')
            record = out / name
            record.mkdir()
            bundle = record / 'bundle'
            source, compose = prepare(bundle, args.supervisor_source, enabled,
                runtime_source=RUNTIME, python_home=PYHOME, budget_enabled=False, historical_config=True)
            logs, gateway_logs = record / 'logs', record / 'gateway_logs'
            logs.mkdir(); gateway_logs.mkdir()
            config = json.loads(compose.read_text())
            # Use the actual prepared topology; only engineering command and fake
            # upstream replacement differ. No remote provider or telemetry route.
            main = config['services']['main']
            main.update(image=image, read_only=True, working_dir='/logs',
                entrypoint=[PYTHON, '/checks/container_entry.py'])
            main['volumes'].extend([f'{source.as_posix()}:/opt/genericagent-source:ro',
                f'{RUNTIME.as_posix()}:/opt/m4-runtime:ro', f'{HERE.as_posix()}:/checks:ro', f'{logs.as_posix()}:/logs:rw'])
            main['environment'].update(PYTHONDONTWRITEBYTECODE='1',
                PYTHONPATH='/opt/m4-runtime/ga-env/lib/python3.12/site-packages:/opt/genericagent-source')
            gateway = config['services']['model-gateway']
            gateway.update(image=GATEWAY_IMAGE, network_mode='none', entrypoint=[PYTHON, '/checks/fake_gateway.py'])
            gateway['environment']['PYTHONDONTWRITEBYTECODE'] = '1'
            gateway['volumes'].extend([f'{HERE.as_posix()}:/checks:ro', f'{gateway_logs.as_posix()}:/gateway-logs:rw'])
            compose.write_text(json.dumps(config, indent=2))
            project = 'm1-p-engineering-' + name.replace('_', '-')
            prefix = ['docker', 'compose', '-p', project, '-f', str(compose)]
            receipt = command(prefix + ['up', '--pull', 'never', '--abort-on-container-exit', '--exit-code-from', 'main'])
            (record / 'launch.json').write_text(json.dumps(receipt, indent=2))
            ids = command(prefix + ['ps', '-a', '-q'])
            container_ids = ids['stdout'].split()
            inspection = command(['docker', 'inspect', *container_ids]) if container_ids else ids
            (record / 'container_inspect.json').write_text(json.dumps(inspection, indent=2))
            rawlogs = command(prefix + ['logs', '--no-color'])
            (record / 'compose_logs.json').write_text(json.dumps(rawlogs, indent=2))
            cleanup = command(prefix + ['down', '-v'])
            (record / 'cleanup.json').write_text(json.dumps(cleanup, indent=2))
            if receipt['returncode'] != 0:
                raise RuntimeError('Linux launch check failed; retained at ' + str(record))
            capture = json.loads((logs / 'capture.json').read_text())
            routed = json.loads((gateway_logs / 'requests.json').read_text())
            assert len(capture['requests']) == 5 and len(routed) == 6
            assert capture['budget'] is None and capture['platform']['os'].startswith('Linux')
            assert all(Path(p).is_relative_to('/opt/genericagent-source/monitor_agent_core') for p in capture['modules'].values())
            assert capture['network'] == {'external_http_attempts': 0, 'socket_attempts': 0}
            for sent, received in zip(capture['requests'] + capture['task_transport_requests'], routed):
                assert sent['payload'] == received['payload']
            state = capture['final_working']
            assert 'original artifact read' in state and 'DCEC-CONTROL' not in state
            assert 'bash' in json.dumps(capture['requests'][0]['payload']['tools'])
            for container in json.loads(inspection['stdout']):
                assert container['HostConfig']['NetworkMode'] == 'none'
                assert container['HostConfig']['CapDrop'] == ['ALL']
            captures.append(capture)
            summary['records'].append({'case': case, 'policy_enabled': enabled,
                'image': image, 'request_count': 6, 'captured_worker': str((logs / 'capture.json').relative_to(out)),
                'capture_sha256': sha((logs / 'capture.json').read_bytes()), 'budget_wrapper_enabled': False})
        normalizations = []
        for a, b in zip(captures[0]['requests'], captures[1]['requests']):
            x, sx = normalized(a['payload'], captures[0]); y, sy = normalized(b['payload'], captures[1])
            assert y['system'].count(body) == 1 and body not in x['system']
            y['system'] = y['system'].replace('\n\n' + body, '', 1)
            assert x == y, 'difference outside declared policy/mechanical session IDs'
            normalizations.append({'m1': sx, 'm1_p': sy})
        assert captures[0]['task_transport_requests'][0]['payload'] == captures[1]['task_transport_requests'][0]['payload']
        summary['comparisons'].append({'case': case, 'only_policy_difference_after_declared_session_mapping': True,
            'session_mappings': normalizations, 'raw_payloads_retained': True})
    (out / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()
