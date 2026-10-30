"""Pinned, dependency-only bundles for frozen GA native evaluations.

Bundles are built in disposable base-image containers. They contain no Task
workspace, verifier tests, model traffic or scoring output. The host verifies
the exact bundle before preparation; the verifier restores it only after the
agent writers have stopped and before the official test script starts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex
from tempfile import TemporaryDirectory
import uuid

from .evaluation_cache import _archive_index

PROTOCOL = 'prepared_dependency_bundle_v1'
SCHEMAS = {
    'apt_curl_uvx': 'ga20-apt-uv-dependency-prototype-v1',
    'pip': 'ga20-pip-dependency-prototype-v1',
    'uvx': 'ga20-uvx-dependency-prototype-v1',
}
SAFE = re.compile(r'[A-Za-z0-9_.+\-=]+\Z')
ISOLATED_UVX_LAYOUT = 'isolated_evaluation_uvx_v1'
ISOLATED_UVX_ROOT = 'var/cache/evaluation-uvx'


def uvx_environment(manifest, *, offline):
    """Keep an evaluation-only uv cache separate from the Task's uv sync."""
    if manifest.get('cache_layout') != ISOLATED_UVX_LAYOUT:
        return 'HOME=/root ' + ('UV_OFFLINE=1 ' if offline else '') + \
            'UV_PYTHON_DOWNLOADS=never UV_PYTHON_PREFERENCE=only-managed '
    return ('HOME=/root UV_CACHE_DIR=/' + ISOLATED_UVX_ROOT + '/cache '
            'UV_PYTHON_INSTALL_DIR=/' + ISOLATED_UVX_ROOT + '/python '
            'UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never '
            'UV_PYTHON_PREFERENCE=only-managed ')


def verifier_test_command(command, manifest):
    """Apply evaluation-only env without changing the official test script."""
    if manifest.get('cache_layout') != ISOLATED_UVX_LAYOUT:
        return command
    return 'env ' + uvx_environment(manifest, offline=True) + 'sh -c ' + shlex.quote(command)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_bundle(cache, *, task, image_digest, image_id, original_sha256,
                  coverage):
    """Check frozen identity, offline acceptance, tar bytes and safe members."""
    if not isinstance(cache, dict) or set(cache) != {'bundle_path', 'manifest_sha256'}:
        raise ValueError('invalid prepared dependency cache binding')
    supplied = Path(cache['bundle_path'])
    if supplied.is_symlink():
        raise ValueError('prepared dependency cache must not be a symlink')
    root = supplied.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('prepared dependency cache must be a real directory')
    manifest_path, payload = root / 'manifest.json', root / 'payload.tar'
    if not re.fullmatch(r'[0-9a-f]{64}', cache['manifest_sha256']) or \
            sha(manifest_path) != cache['manifest_sha256']:
        raise ValueError('prepared dependency manifest hash differs')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (manifest.get('schema') != SCHEMAS.get(coverage) or
            manifest.get('status') != 'clean_container_offline_ready' or
            manifest.get('task') != task or
            manifest.get('image_repo_digest') != image_digest or
            manifest.get('image_id') != image_id or
            manifest.get('original_test_sha256') != original_sha256 or
            not re.fullmatch(r'[0-9a-f]{64}', str(manifest.get('payload_sha256'))) or
            sha(payload) != manifest['payload_sha256'] or
            _archive_index(payload, extra_roots=(ISOLATED_UVX_ROOT,)
                if manifest.get('cache_layout') == ISOLATED_UVX_LAYOUT else ()) !=
                manifest.get('files')):
        raise ValueError('prepared dependency bundle identity or bytes differ')
    package_field = 'pip_packages' if coverage == 'pip' else 'uv_wheels'
    packages = manifest.get(package_field)
    if not isinstance(packages, list) or not packages or any(
            not isinstance(item, str) or not SAFE.fullmatch(item) or '==' not in item
            for item in packages):
        raise ValueError('prepared dependency package identity invalid')
    if coverage == 'pip' and (not isinstance(manifest.get('pip_flags'), list) or
            any(flag != '--break-system-packages' for flag in manifest['pip_flags'])):
        raise ValueError('prepared pip flags invalid')
    if coverage == 'apt_curl_uvx' and (not isinstance(manifest.get('apt'), list) or
            not manifest['apt'] or any(not SAFE.fullmatch(item) for item in manifest['apt'])):
        raise ValueError('prepared apt package identity invalid')
    layout = manifest.get('cache_layout')
    if layout is not None:
        if coverage != 'uvx' or layout != ISOLATED_UVX_LAYOUT or any(
                name != ISOLATED_UVX_ROOT and
                not name.startswith(ISOLATED_UVX_ROOT + '/')
                for name in manifest['files']):
            raise ValueError('prepared evaluation cache layout invalid')
    for name in ('builder.exit.json', 'offline.exit.json'):
        if json.loads((root / name).read_text(encoding='utf-8')) != {'exit_code': 0}:
            raise ValueError('prepared dependency builder or offline check failed')
    return manifest


def _preflight_script(files):
    """Check only paths the archive will touch, not unrelated base-image links."""
    parents = set()
    for name in files:
        parents.update(str(parent) for parent in PurePosixPath(name).parents
                       if str(parent) != '.')
    lines = ['#!/bin/sh', 'set -eu']
    detach = []
    for name in sorted(parents, key=lambda path: (path.count('/'), path)):
        path = shlex.quote('/' + name)
        lines.append(f'if [ -L {path} ] || {{ [ -e {path} ] && [ ! -d {path} ]; }}; '
                     f'then echo {shlex.quote("unsafe parent: " + name)} >&2; exit 3; fi')
    for name, row in sorted(files.items()):
        path = shlex.quote('/' + name)
        if row['type'] == 'symlink':
            target = shlex.quote(row['target'])
            lines.append(f'if [ -e {path} ] && [ ! -L {path} ]; '
                         f'then echo {shlex.quote("unsafe link: " + name)} >&2; exit 3; fi')
            lines.append(f'if [ -L {path} ] && [ "$(readlink {path})" != {target} ]; '
                         f'then echo {shlex.quote("different link: " + name)} >&2; exit 3; fi')
        elif row['type'] == 'file':
            lines.append(f'if [ -L {path} ] || {{ [ -e {path} ] && [ ! -f {path} ]; }}; '
                         f'then echo {shlex.quote("unsafe file: " + name)} >&2; exit 3; fi')
            # GNU tar may otherwise mutate a hardlinked base-image file outside
            # this cache path. Detach only after every destination is checked.
            temporary = shlex.quote('/' + name + '.XXXXXX')
            detach.append(f'if [ -f {path} ] && [ "$(stat -c %h {path})" != 1 ]; '
                          f'then t=$(mktemp {temporary}); cp -p -- {path} "$t"; '
                          f'mv -f -- "$t" {path}; fi')
        else:
            lines.append(f'if [ -L {path} ] || {{ [ -e {path} ] && [ ! -d {path} ]; }}; '
                         f'then echo {shlex.quote("unsafe directory: " + name)} >&2; exit 3; fi')
    return ('\n'.join(lines + detach) + '\n').encode('utf-8')


async def restore(exec_command, upload_file, cache, manifest, record):
    """Upload a verified bundle into this verifier, install offline, clean stage."""
    root = Path(cache['bundle_path'])
    remote = '/tmp/ga-eval-deps-' + uuid.uuid4().hex

    async def execute(stage, command):
        result = await exec_command(command=command, user='root', timeout_sec=600)
        record({'stage': stage, 'protocol': PROTOCOL,
                'return_code': result.return_code})
        if result.return_code:
            raise RuntimeError(stage + ' failed; dependency bundle not ready')

    await execute('cache_stage', 'mkdir -m 700 ' + remote)
    try:
        await upload_file(source_path=root / 'payload.tar', target_path=remote + '/payload.tar')
        expected = manifest['payload_sha256']
        await execute('cache_readback',
                      f'echo "{expected}  {remote}/payload.tar" | sha256sum -c -')
        with TemporaryDirectory(prefix='ga-eval-preflight-') as temporary:
            script = Path(temporary) / 'preflight.sh'
            script.write_bytes(_preflight_script(manifest['files']))
            await upload_file(source_path=script, target_path=remote + '/preflight.sh')
            await execute('cache_preflight_readback',
                f'echo "{sha(script)}  {remote}/preflight.sh" | sha256sum -c -')
        await execute('cache_destination_preflight', 'sh ' + remote + '/preflight.sh')
        await execute('cache_restore',
                      f'tar --no-same-owner -xf {remote}/payload.tar -C /')
        schema = manifest['schema']
        if schema == SCHEMAS['apt_curl_uvx']:
            await execute('cache_deb_install',
                          'dpkg -i /var/cache/evaluation-debs/*.deb')
        if schema == SCHEMAS['pip']:
            packages = ' '.join(shlex.quote(item) for item in manifest['pip_packages'])
            flags = ' '.join(shlex.quote(item) for item in manifest['pip_flags'])
            await execute('cache_pip_install',
                          'pip install --no-index --find-links '
                          '/var/cache/evaluation-debs/wheels ' + flags + ' ' + packages)
        else:
            wheels = ' '.join('-w ' + shlex.quote(item)
                              for item in manifest['uv_wheels'])
            uvx = ('/root/.local/bin/uvx' if schema == SCHEMAS['apt_curl_uvx']
                   else 'uvx')
            await execute('cache_uv_offline_check',
                          'cd /tmp && ' + uvx_environment(manifest, offline=True) + uvx +
                          ' --offline -p 3.13 ' + wheels +
                          " python -c 'import sys; print(sys.version.split()[0])'")
    finally:
        await execute('cache_stage_cleanup', 'rm -rf -- ' + remote)
