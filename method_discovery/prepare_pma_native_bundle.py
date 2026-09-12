"""Prepare native PMA transport files without starting Docker or a model.

Credential JSON must be supplied privately as {base, key}. No credentials are
accepted on the command line or printed. Task selection is a separate gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from pma_native_support import gateway_config
from prepare_pma_linux_controller import SCRIPTS

ROOT = Path(__file__).resolve().parents[1]
# Local images may not have a repository digest, so pin the local image ID.
IMAGE = 'sha256:6731421eb17a89e7a11d435697fe0770ab685471c520980966cbef52296da4b3'


def prepare(output, credentials):
    output = Path(output).resolve()
    if output.drive.upper() != 'E:':
        raise ValueError('Checked Desktop bind mapping requires E drive')
    route = gateway_config(credentials['base'], credentials['key'])
    output.mkdir(parents=True, exist_ok=False)
    private = output / 'private'
    private.mkdir()
    (private / 'gateway.json').write_text(json.dumps(route), encoding='utf-8')
    source = output / 'runtime'
    source.mkdir()
    for name in (*SCRIPTS, 'pma_native_entry.py'):
        shutil.copy2(ROOT / 'method_discovery' / name, source / name)
    shutil.copy2(ROOT / 'long_context_bench/adapters/isolated_transport.py',
                 source / 'isolated_transport.py')
    work = output / 'work'
    work.mkdir()
    linux_work = '/run/desktop/mnt/host/e/' + work.relative_to('E:/').as_posix()
    common = {'image': IMAGE, 'read_only': True, 'cap_drop': ['ALL'],
              'security_opt': ['no-new-privileges:true'],
              'tmpfs': ['/tmp:rw,size=256m']}
    compose = {'services': {
        'gateway': {**common, 'network_mode': 'bridge',
            'volumes': [f'{source.as_posix()}:/runtime:ro',
                        f'{private.as_posix()}:/private:ro', 'channel:/run/model-channel'],
            'command': ['python', '/runtime/isolated_transport.py', 'gateway',
                        '--config', '/private/gateway.json'],
            'healthcheck': {'test': ['CMD', 'python', '-c',
                "import socket; s=socket.socket(socket.AF_UNIX); s.connect('/run/model-channel/gateway.sock'); s.close()"],
                'interval': '1s', 'timeout': '3s', 'retries': 30}},
        'controller': {**common, 'network_mode': 'none', 'cpus': 2, 'mem_limit': '2g',
            'volumes': [f'{source.as_posix()}:/workspace/method_discovery:ro',
                        f'{work.as_posix()}:{linux_work}',
                        'channel:/run/model-channel:ro',
                        '/var/run/docker.sock:/var/run/docker.sock'],
            'depends_on': {'gateway': {'condition': 'service_healthy'}},
            # Default command is tests, never an implicit real run.
            'command': ['python', '-m', 'unittest', 'discover', '-s', 'method_discovery',
                        '-p', 'test_pma_native*.py', '-v']},
    }, 'volumes': {'channel': {}}}
    (output / 'compose.json').write_text(json.dumps(compose, indent=2), encoding='utf-8')
    identity = {'status': 'prepared_not_executed', 'api_calls': 0,
        'controller_image': IMAGE, 'task_selected': False,
        'provider_difference': 'CC-VIBE Anthropic transport instead of OpenRouter',
        'runtime_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in source.iterdir()}, 'linux_work': linux_work}
    (output / 'identity.json').write_text(json.dumps(identity, indent=2), encoding='utf-8')
    return identity


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--credentials-file', required=True)
    args = parser.parse_args()
    identity = prepare(args.output, json.loads(Path(args.credentials_file).read_text(encoding='utf-8')))
    print(json.dumps(identity))
