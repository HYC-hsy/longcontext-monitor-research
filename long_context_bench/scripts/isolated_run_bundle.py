"""Build a per-run, non-public task plus a fixed inference socket gateway."""
import hashlib
import json
import runpy
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from requests.certs import where as requests_ca_where


PORT = 18765
PROFILE = 'no-network-unix-inference-v1'
CONTAINER_CA_PREFIX = '/gateway/ca'


def production_tls_semantics(profile, *, ca_file):
    """Mirror the audited production requests TLS/proxy contract for one route."""
    if profile.get('proxy'):
        raise ValueError('External provider proxies need explicit isolation review')
    verify = profile.get('verify', True)
    if verify is True:
        ca_path = Path(requests_ca_where()).resolve()
        source_kind = 'production_requests_certifi'
    elif verify is False:
        ca_path = None
        source_kind = 'production_profile_verify_false'
    elif isinstance(verify, str) and verify:
        ca_path = Path(verify).expanduser().resolve()
        source_kind = 'production_profile_ca_path'
    else:
        raise ValueError(f'Unsupported production verify setting: {type(verify).__name__}')
    if ca_path is not None and not ca_path.is_file():
        raise FileNotFoundError(f'Production CA bundle is missing: {ca_path}')
    return ({
        'verification_enabled': verify is not False,
        'verify_value_class': 'bool' if isinstance(verify, bool) else 'path',
        'ca_source_kind': source_kind,
        'ca_file': ca_file if ca_path is not None else None,
        'ca_bundle_sha256': hashlib.sha256(ca_path.read_bytes()).hexdigest()
            if ca_path is not None else None,
        'production_proxy_present': False,
    }, ca_path)


def digest_tree(root):
    digest = hashlib.sha256()
    for p in sorted(root.rglob('*')):
        if p.is_file():
            digest.update(p.relative_to(root).as_posix().encode() + b'\0')
            digest.update(p.read_bytes())
    return digest.hexdigest()


def build_bundle(root, source, runtime, python_home, task_config, monitor_config,
                 collector_port, monitor_profile_path=None):
    """No Docker/API calls. Output includes a private gateway credential file."""
    root, source, runtime = Path(root), Path(source), Path(runtime)
    root.mkdir(parents=True, exist_ok=False)
    copied = root / 'source'
    copied.mkdir()
    # Do not expose checkout docs, test fixtures, old trajectories, or actual keys.
    for p in source.glob('*.py'):
        if p.is_symlink():
            raise ValueError('Runtime source must not contain symbolic links')
        if not p.name.startswith('mykey'):
            shutil.copy2(p, copied / p.name)
    for name in ('assets', 'memory', 'plugins', 'monitor_agent_core', 'pma_baseline', 'reflect',
                 'ga_cli', 'frontends'):
        p = source / name
        if p.exists():
            if name == 'memory':
                # Keep frozen generic SOP files, never mount historical sessions.
                (copied / name).mkdir()
                for item in p.iterdir():
                    if item.is_symlink():
                        raise ValueError('Memory snapshot contains a symbolic link')
                    if item.is_file() and item.suffix in {'.py', '.md', '.txt'}:
                        shutil.copy2(item, copied / name / item.name)
                continue
            if any(x.is_symlink() for x in p.rglob('*')):
                raise ValueError('Runtime snapshot must not contain symbolic links')
            shutil.copytree(p, copied / name, ignore=shutil.ignore_patterns(
                '__pycache__', 'tests', '.git', '*.pyc', '*.local.json', 'file_access_stats.json'))
    configs = runpy.run_path(str(source / 'mykey.py'))
    gateway = {'models': {}, 'telemetry': f'http://host.docker.internal:{collector_port}/v1/traces'}
    client_configs = {}
    independent = json.loads(Path(monitor_profile_path).read_text(encoding='utf-8')) if monitor_profile_path else None
    monitor_clients = {}
    ca_sources = {}
    for role, name in [('task', task_config), ('monitor', monitor_config)]:
        cfg = dict(independent[name] if role == 'monitor' and independent is not None else configs[name])
        endpoint = urlsplit(cfg['apibase'])
        if endpoint.scheme != 'https' or not endpoint.hostname or endpoint.query or endpoint.fragment:
            raise ValueError('Gateway requires a fixed HTTPS inference base')
        container_ca = f'{CONTAINER_CA_PREFIX}-{role}.pem'
        tls, ca_path = production_tls_semantics(cfg, ca_file=container_ca)
        ca_sources[role] = ca_path
        model = cfg['model']
        route_id = 'monitor' if role == 'monitor' and independent is not None else model
        if route_id in gateway['models']:
            raise ValueError('Ambiguous duplicate model route')
        key = cfg['apikey']
        headers = {'x-api-key': key} if key.startswith('sk-ant-') else {'Authorization': 'Bearer ' + key}
        paths = ['/v1/messages'] if 'claude' in model.lower() else ['/v1/responses']
        gateway['models'][route_id] = {
            'base': cfg['apibase'], 'headers': headers, 'paths': paths,
            'model': model, 'tls': tls,
        }
        cfg.update(apikey='isolated-local-channel', apibase=f'http://127.0.0.1:{PORT}')
        cfg.pop('proxy', None)
        if role == 'monitor' and independent is not None:
            cfg['transport_route'] = route_id
            monitor_clients[name] = cfg
        else:
            client_configs[name] = cfg
    (copied / 'mykey.json').write_text(json.dumps(client_configs), encoding='utf-8')
    if monitor_clients:
        (copied / 'monitor_agent_core' / 'models.local.json').write_text(json.dumps(monitor_clients), encoding='utf-8')
    private = root / 'gateway'
    private.mkdir()
    for role, ca_path in ca_sources.items():
        if ca_path is not None:
            shutil.copy2(ca_path, private / f'ca-{role}.pem')
    (private / 'config.json').write_text(json.dumps(gateway), encoding='utf-8')
    transport = Path(__file__).resolve().parents[1] / 'adapters/isolated_transport.py'
    shutil.copy2(transport, private / 'transport.py')
    shutil.copy2(transport, copied / 'isolated_transport.py')
    python_bin = f'/opt/m4-runtime/python/{python_home}/bin/python3.12'
    compose = {
        'services': {
            'main': {
                'network_mode': 'none', 'cap_drop': ['ALL'],
                'security_opt': ['no-new-privileges:true'],
                'volumes': ['model-channel:/run/model-channel:ro'],
                'depends_on': {'model-gateway': {'condition': 'service_healthy'}},
            },
            'model-gateway': {
                'image': 'debian:bookworm-slim', 'network_mode': 'bridge',
                'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
                'read_only': True,
                'environment': {'SSL_CERT_FILE':
                    '/opt/m4-runtime/ga-env/lib/python3.12/site-packages/certifi/cacert.pem'},
                'volumes': [f'{runtime.resolve().as_posix()}:/opt/m4-runtime:ro',
                            f'{private.resolve().as_posix()}:/gateway:ro',
                            'model-channel:/run/model-channel'],
                'entrypoint': [python_bin, '/gateway/transport.py', 'gateway',
                               '--config', '/gateway/config.json'],
                'healthcheck': {'test': ['CMD', python_bin, '-c',
                    "import socket; s=socket.socket(socket.AF_UNIX); s.connect('/run/model-channel/gateway.sock'); s.close()"],
                    'interval': '1s', 'timeout': '3s', 'retries': 30},
            },
        },
        'volumes': {'model-channel': {}},
    }
    compose_path = root / 'isolation.compose.json'
    compose_path.write_text(json.dumps(compose, indent=2), encoding='utf-8')
    evidence = {'profile': PROFILE, 'snapshot_sha256': digest_tree(copied),
                'source_mount': str(copied), 'model_names': list(gateway['models']),
                'secrets_in_evidence': False, 'task_network_mode': 'none',
                'gateway_transport_sha256': hashlib.sha256(transport.read_bytes()).hexdigest()}
    (root / 'isolation_identity.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    return copied, compose_path
