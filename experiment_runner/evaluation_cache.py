"""Host-persistent SQLite dependency bundles. No network fallback or test execution.

Integrate only after the agent is stopped and original verifier bytes are checked.
Use evaluation_bootstrap.effective_script unchanged; select persistent_bundle_v1
explicitly, never silently replace bootstrap_retry_v1. Bundles are trusted build
artifacts, not a sandbox for untrusted executables. SHA256 detects corruption,
not a malicious builder. Pin the expected identity in the run specification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid
from pathlib import Path, PurePosixPath

PROTOCOL = 'persistent_bundle_v1'
ORIGINAL_SHA256 = '4770437ea96c3cc84684b4f99d55fb148fcac09f9ea1e8ef49de487716e6c334'
ROOTS = ('root/.local/share/uv/python', 'root/.cache/uv', 'var/cache/evaluation-debs')
BIN_FILES = ('root/.local/bin/uv', 'root/.local/bin/uvx', 'root/.local/bin/env')
VERSIONS = {'uv': '0.9.5', 'pytest': '8.4.1', 'pytest-json-ctrf': '0.3.5'}


class CacheMiss(RuntimeError):
    """Explicit terminal dependency failure; callers must not download on miss."""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def _sha(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _allowed(name):
    p = PurePosixPath(name)
    return (not p.is_absolute() and str(p) == name and '..' not in p.parts
            and (name in BIN_FILES or any(name == r or name.startswith(r + '/') for r in ROOTS)))


def _link_target(name, target, *, extra_roots=()):
    if target.startswith('/'):
        result = target[1:]
    else:
        parts = list(PurePosixPath(name).parent.parts)
        for part in target.split('/'):
            if part == '..':
                if not parts:
                    raise CacheMiss('link escapes bundle')
                parts.pop()
            elif part not in ('', '.'):
                parts.append(part)
        result = '/'.join(parts)
    if not (_allowed(result) or any(
            result == root or result.startswith(root + '/') for root in extra_roots)):
        raise CacheMiss('link target outside dependency allowlist')
    return result


def validate_identity(identity):
    keys = {'protocol', 'task', 'original_sha256', 'base_image', 'os_id',
            'os_version', 'architecture', 'python', 'python_executable', 'versions'}
    if not isinstance(identity, dict) or set(identity) != keys:
        raise CacheMiss('invalid identity fields')
    if (identity['protocol'] != PROTOCOL or identity['task'] != 'sqlite-with-gcov'
            or identity['original_sha256'] != ORIGINAL_SHA256
            or identity['versions'] != VERSIONS
            or not re.fullmatch(r'[^\s@]+@sha256:[0-9a-f]{64}', identity['base_image'])
            or identity['os_id'] != 'ubuntu'
            or not re.fullmatch(r'\d+\.\d+', identity['os_version'])
            or identity['architecture'] not in ('x86_64', 'aarch64')
            or not re.fullmatch(r'3\.13\.\d+', identity['python'])):
        raise CacheMiss('unsupported bundle identity')
    executable = identity['python_executable']
    if not isinstance(executable, str) or not executable.startswith('/' + ROOTS[0] + '/') or not _allowed(executable[1:]):
        raise CacheMiss('invalid Python executable')
    return hashlib.sha256(_json(identity)).hexdigest()


def _archive_index(archive, *, extra_roots=()):
    rows = {}
    with tarfile.open(archive, 'r:') as tar:
        for item in tar:
            allowed = _allowed(item.name) or any(
                item.name == root or item.name.startswith(root + '/')
                for root in extra_roots)
            if item.name in rows or not allowed or item.mode & 0o7000:
                raise CacheMiss('unsafe or duplicate archive member: ' + item.name)
            if item.isfile():
                stream = tar.extractfile(item)
                row = {'type': 'file', 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest(), 'mode': item.mode, 'size': item.size}
            elif item.isdir():
                row = {'type': 'directory', 'mode': item.mode}
            elif item.issym():
                _link_target(item.name, item.linkname, extra_roots=extra_roots)
                row = {'type': 'symlink', 'target': item.linkname, 'mode': item.mode}
            else:
                raise CacheMiss('hardlinks/devices/FIFOs are forbidden')
            rows[item.name] = row
    for name, row in rows.items():
        if any(rows.get(str(parent), {}).get('type') == 'symlink' for parent in PurePosixPath(name).parents):
            raise CacheMiss('member under symlink')
        if row['type'] == 'symlink':
            seen = {name}
            target = _link_target(name, row['target'], extra_roots=extra_roots)
            while rows.get(target, {}).get('type') == 'symlink':
                if target in seen:
                    raise CacheMiss('cyclic symlink')
                seen.add(target)
                target = _link_target(target, rows[target]['target'], extra_roots=extra_roots)
            if target not in rows:
                raise CacheMiss('dangling dependency symlink')
    return rows


def verify_bundle(bundle, expected_identity, *, _allow_staging=False):
    """Validate identity, completion marker, archive hash and every member hash."""
    try:
        bundle = Path(bundle)
        key = validate_identity(expected_identity)
        if bundle.name.startswith('.building-') and not _allow_staging:
            raise CacheMiss('bundle not atomically published')
        if bundle.is_symlink() or not bundle.is_dir():
            raise CacheMiss('bundle absent or symlink')
        for name in ('manifest.json', 'payload.tar', 'COMPLETE'):
            if not (bundle / name).is_file() or (bundle / name).is_symlink():
                raise CacheMiss('bundle incomplete')
        raw = (bundle / 'manifest.json').read_bytes()
        manifest = json.loads(raw)
        if (bundle / 'COMPLETE').read_text().strip() != hashlib.sha256(raw).hexdigest():
            raise CacheMiss('unpublished or damaged manifest')
        if manifest['identity'] != expected_identity or manifest['key'] != key:
            raise CacheMiss('bundle identity mismatch')
        if _sha(bundle / 'payload.tar') != manifest['payload_sha256']:
            raise CacheMiss('payload checksum mismatch')
        rows = _archive_index(bundle / 'payload.tar')
        if rows != manifest['files']:
            raise CacheMiss('dependency file inventory mismatch')
        required = (*BIN_FILES, expected_identity['python_executable'][1:])
        if any(rows.get(name, {}).get('type') != 'file' for name in required):
            raise CacheMiss('required dependency missing')
        if not any(n.startswith(ROOTS[2] + '/') and n.endswith('.deb') and r['type'] == 'file' for n, r in rows.items()):
            raise CacheMiss('curl deb closure missing')
        if not any(n.startswith(ROOTS[1] + '/') and r['type'] == 'file' for n, r in rows.items()):
            raise CacheMiss('uv cache missing')
        return manifest
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as exc:
        raise CacheMiss('invalid bundle: ' + str(exc)) from exc


def publish_bundle(source_root, cache_root, identity):
    """Atomically publish immutable key directory; never replace existing entries.

    Linux builder only (directory fsync). source_root must be a clean dependency-
    only builder, not an agent filesystem.
    Staging directories cannot count as hits. A crashed writer leaves only staging.
    """
    key = validate_identity(identity)
    source_root, cache_root = Path(source_root), Path(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    target = cache_root / key
    if target.exists():
        verify_bundle(target, identity)
        return target
    staging = Path(tempfile.mkdtemp(prefix='.building-', dir=cache_root))
    try:
        with tarfile.open(staging / 'payload.tar', 'w', dereference=False) as tar:
            for name in (*BIN_FILES, *ROOTS):
                source = source_root / name
                if source.is_symlink():
                    raise CacheMiss('top-level dependency path is a symlink')
                if not source.exists():
                    raise CacheMiss('missing source dependency: ' + name)
                # recursive tar collection retains absolute and relative uv links.
                paths = [source]
                if source.is_dir():
                    paths += sorted(source.rglob('*'))
                for path in paths:
                    # uv uses hardlinked cache entries; store their bytes separately,
                    # but retain symlinks (including absolute interpreter links).
                    tar.inodes.clear()
                    tar.add(path, arcname=path.relative_to(source_root).as_posix(), recursive=False)
        files = _archive_index(staging / 'payload.tar')
        manifest = {'identity': identity, 'key': key, 'files': files,
                    'payload_sha256': _sha(staging / 'payload.tar')}
        raw = _json(manifest)
        (staging / 'manifest.json').write_bytes(raw)
        (staging / 'COMPLETE').write_text(hashlib.sha256(raw).hexdigest() + '\n')
        verify_bundle(staging, identity, _allow_staging=True)
        if os.name == 'posix':
            for name in ('payload.tar', 'manifest.json', 'COMPLETE'):
                with open(staging / name, 'rb') as stream:
                    os.fsync(stream.fileno())
        # mkdir lock, unlike rename over a directory, does not overwrite a racer.
        lock = cache_root / ('.publish-' + key)
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise CacheMiss('publication busy or interrupted; inspect lock explicitly') from exc
        try:
            if target.exists():
                verify_bundle(target, identity)
            else:
                staging.rename(target)
                if os.name == 'posix':
                    fd = os.open(cache_root, os.O_RDONLY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
        finally:
            lock.rmdir()
        return target
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _safe_destination(root, name):
    path = root / name
    for parent in reversed(path.parents):
        if parent == root.parent:
            continue
        if parent == root or root in parent.parents:
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise CacheMiss('unsafe destination ancestor: ' + str(parent))
    if path.exists() and path.is_file() and path.stat().st_nlink > 1:
        raise CacheMiss('refuse hardlinked destination: ' + str(path))
    if path.is_symlink():
        raise CacheMiss('refuse existing destination symlink: ' + str(path))
    return path


def restore_bundle(bundle, identity, destination='/'):
    """Restore only allowlisted members, rejecting destination symlink traversal."""
    manifest = verify_bundle(bundle, identity)
    destination = Path(destination)
    # Preflight all paths before any writes. Existing ordinary dependency files may
    # be replaced, but existing links fail closed rather than following them.
    for name in manifest['files']:
        _safe_destination(destination, name)
    # Fail closed on old/Task-created dependency residue; never delete Task data.
    # Especially important for debs: no unmanifested package may be installed.
    for name in ROOTS:
        existing = _safe_destination(destination, name)
        if existing.exists():
            for path in existing.rglob('*'):
                relative = path.relative_to(destination).as_posix()
                if relative not in manifest['files']:
                    raise CacheMiss('unlisted destination dependency: ' + relative)
    with tarfile.open(Path(bundle) / 'payload.tar', 'r:') as tar:
        members = tar.getmembers()
        for item in members:
            if item.issym():
                continue
            path = _safe_destination(destination, item.name)
            if item.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(item) as source, open(path, 'wb') as target:
                    shutil.copyfileobj(source, target)
                os.chmod(path, item.mode)
        for item in members:
            if item.issym():
                path = _safe_destination(destination, item.name)
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    raise CacheMiss('symlink destination already exists')
                path.symlink_to(item.linkname)
    return manifest


def install_manifest_debs(manifest):
    paths = ['/' + name for name, row in sorted(manifest['files'].items())
             if row['type'] == 'file' and name.startswith(ROOTS[2] + '/') and name.endswith('.deb')]
    if not paths:
        raise CacheMiss('manifest has no deb packages')
    subprocess.run(['dpkg', '-i', *paths], check=True, shell=False)


def offline_check(identity):
    """Run dependency metadata/help only, from an empty directory, without fetching."""
    actual = platform.freedesktop_os_release()
    if (actual['ID'] != identity['os_id'] or actual['VERSION_ID'] != identity['os_version']
            or platform.machine() != identity['architecture']):
        raise CacheMiss('container OS/architecture mismatch')
    env = {**os.environ, 'HOME': '/root', 'UV_OFFLINE': '1', 'UV_PYTHON_DOWNLOADS': 'never',
           'UV_CACHE_DIR': '/root/.cache/uv', 'UV_PYTHON_INSTALL_DIR': '/root/.local/share/uv/python',
           'UV_PYTHON_PREFERENCE': 'only-managed', 'UV_NO_CONFIG': '1',
           'PYTHONNOUSERSITE': '1'}
    for name in list(env):
        if name.startswith('PYTEST_') or name in ('PYTHONPATH', 'PYTHONHOME'):
            env.pop(name)
    env['PATH'] = '/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
    with tempfile.TemporaryDirectory(prefix='eval-dep-check-') as directory:
        def run(args):
            return subprocess.check_output(args, env=env, cwd=directory, text=True, stderr=subprocess.STDOUT)
        for binary in ('uv', 'uvx'):
            if not re.match(r'^' + binary + r' 0\.9\.5(?:\s|$)', run(['/root/.local/bin/' + binary, '--version'])):
                raise CacheMiss('uv version mismatch')
        run(['curl', '--version'])
        args = ['/root/.local/bin/uvx', '--offline', '-p', '3.13', '-w', 'pytest==8.4.1', '-w', 'pytest-json-ctrf==0.3.5']
        code = 'import sys,importlib.metadata as m,json;print(json.dumps([sys.version.split()[0],m.version("pytest"),m.version("pytest-json-ctrf")]))'
        if json.loads(run(args + ['python', '-c', code])) != [identity['python'], '8.4.1', '0.3.5']:
            raise CacheMiss('resolved Python/package version mismatch')
        if '--ctrf' not in run(args + ['pytest', '--help']):
            raise CacheMiss('CTRf plugin missing')


def require_offline_ready(bundle, expected_manifest_sha256):
    """Acceptance receipt is integrity bookkeeping, not a builder trust certificate."""
    bundle = Path(bundle)
    if not re.fullmatch(r'[0-9a-f]{64}', expected_manifest_sha256):
        raise CacheMiss('run must pin a manifest SHA256')
    if _sha(bundle / 'manifest.json') != expected_manifest_sha256:
        raise CacheMiss('frozen manifest checksum mismatch')
    try:
        ready = bundle / 'OFFLINE_READY.json'
        if ready.is_symlink():
            raise CacheMiss('unsafe acceptance receipt')
        receipt = json.loads(ready.read_text())
        if receipt != {'manifest_sha256': expected_manifest_sha256,
                       'payload_sha256': _sha(bundle / 'payload.tar'),
                       'acceptance': 'clean-docker-network-none-v1'}:
            raise CacheMiss('offline acceptance receipt mismatch')
    except (OSError, ValueError, TypeError) as exc:
        raise CacheMiss('offline acceptance missing or invalid') from exc


async def prepare_cached(exec_command, upload_file, bundle, expected_identity, record, *, expected_manifest_sha256):
    """Use Harbor's root exec/upload_file after writers_stopped is established.

    Caller must attest actual base image digest from container creation metadata;
    it cannot be discovered reliably inside the container. No online fallback.
    """
    manifest = verify_bundle(bundle, expected_identity)
    require_offline_ready(bundle, expected_manifest_sha256)
    helper_sha256 = _sha(Path(__file__))
    record({'stage': 'cache_validated', 'protocol': PROTOCOL,
            'manifest_sha256': expected_manifest_sha256,
            'payload_sha256': manifest['payload_sha256'], 'helper_sha256': helper_sha256})
    remote = '/tmp/eval-bundle-' + uuid.uuid4().hex
    async def execute(stage, command):
        result = await exec_command(command=command, user='root', timeout_sec=600)
        record({'stage': stage, 'protocol': PROTOCOL, 'return_code': result.return_code})
        if result.return_code:
            raise CacheMiss(stage + ' failed: ' + (result.stderr or '')[:500])
        return result
    await execute('cache_stage', 'mkdir -m 700 ' + remote)
    primary_error = None
    try:
        for name in ('payload.tar', 'manifest.json', 'COMPLETE'):
            await upload_file(source_path=Path(bundle) / name, target_path=remote + '/' + name)
        await upload_file(source_path=Path(__file__), target_path=remote + '/evaluation_cache.py')
        # Host-validated tar has no traversal/hardlinks/link-parent members. Extract
        # into a new empty staging root to boot the bundled interpreter, not /.
        python = remote + '/bootstrap' + expected_identity['python_executable']
        identity = shlex.quote(_json(expected_identity).decode())
        command = (f'echo "{expected_manifest_sha256}  {remote}/manifest.json" | sha256sum -c - && '
                   f'echo "{helper_sha256}  {remote}/evaluation_cache.py" | sha256sum -c - && '
                   f'echo "{manifest["payload_sha256"]}  {remote}/payload.tar" | sha256sum -c - && '
                   f'mkdir {remote}/bootstrap && tar --no-same-owner -xf {remote}/payload.tar -C {remote}/bootstrap && '
                   f'{shlex.quote(python)} {remote}/evaluation_cache.py restore {remote} --identity {identity} --install-debs')
        await execute('cache_restore_offline_check', command)
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        # Only the unique directory created above; never prior run artifacts.
        try:
            await execute('cache_stage_cleanup', 'rm -rf -- ' + remote)
        except Exception as exc:
            record({'stage': 'cache_stage_cleanup', 'status': 'failed', 'error_type': type(exc).__name__})
            if primary_error is None:
                raise
    return manifest


def build_bundle(cache_root, base_image):
    """Explicit one-time ONLINE build plus clean Docker --network none acceptance.

    Cross-platform host orchestration: uses the running Python (sys.executable),
    stdlib and Docker only. Bash runs INSIDE the Linux containers, never the host.
    Docker Desktop must be configured for Linux containers and mount access.
    """
    if not re.fullmatch(r'[^\s@]+@sha256:[0-9a-f]{64}', base_image):
        raise CacheMiss('build requires trusted digest-pinned base image')
    root = Path(cache_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    module = Path(__file__).resolve()
    script = module.with_name('sqlite_eval_cache_builder.sh')
    if not script.is_file():
        raise CacheMiss('container builder script missing')
    # Docker Desktop mounts Windows working-tree bytes as-is; the container's
    # Bash must receive LF even when Git checked the script out with CRLF.
    with tempfile.TemporaryDirectory(prefix='eval-builder-') as temporary:
        mounted_script = Path(temporary) / 'build.sh'
        script_bytes = script.read_bytes().replace(b'\r\n', b'\n')
        if b'\r' in script_bytes:
            raise CacheMiss('builder script has unsupported line endings')
        mounted_script.write_bytes(script_bytes)
        online = ['docker', 'run', '--rm', '--user', 'root', '--entrypoint', '/bin/bash',
                  '-e', 'BASE_IMAGE=' + base_image,
                  '-v', str(module) + ':/builder/evaluation_cache.py:ro',
                  '-v', str(mounted_script) + ':/builder/build.sh:ro',
                  '-v', str(root) + ':/output', base_image, '/builder/build.sh']
        result = subprocess.run(online, check=True, shell=False, capture_output=True, text=True)
    lines = [line.removeprefix('BUNDLE=/output/') for line in result.stdout.splitlines()
             if line.startswith('BUNDLE=/output/')]
    if len(lines) != 1 or not re.fullmatch(r'[0-9a-f]{64}', lines[0]):
        raise CacheMiss('builder did not return exactly one valid bundle key')
    path = root / lines[0]
    identity = json.loads((path / 'manifest.json').read_text())['identity']
    if identity['base_image'] != base_image:
        raise CacheMiss('builder base image differs')
    manifest = verify_bundle(path, identity)
    manifest_sha = _sha(path / 'manifest.json')
    python = '/bootstrap' + identity['python_executable']
    command = ('mkdir /bootstrap && '
        f'echo "{manifest_sha}  /bundle/manifest.json" | sha256sum -c - && '
        f'echo "{manifest["payload_sha256"]}  /bundle/payload.tar" | sha256sum -c - && '
        'tar --no-same-owner -xf /bundle/payload.tar -C /bootstrap && '
        f'{shlex.quote(python)} /builder/evaluation_cache.py restore /bundle '
        f'--identity {shlex.quote(json.dumps(identity))} --install-debs')
    offline = ['docker', 'run', '--rm', '--network', 'none', '--user', 'root',
               '--entrypoint', '/bin/bash', '-v', str(path) + ':/bundle:ro',
               '-v', str(module) + ':/builder/evaluation_cache.py:ro', base_image,
               '-euo', 'pipefail', '-c', command]
    subprocess.run(offline, check=True, shell=False)
    # No READY until the independent empty/no-network container has succeeded.
    receipt = {'manifest_sha256': manifest_sha, 'payload_sha256': manifest['payload_sha256'],
               'acceptance': 'clean-docker-network-none-v1'}
    ready = path / 'OFFLINE_READY.json'
    if ready.exists():
        require_offline_ready(path, manifest_sha)
    else:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path, prefix='.ready-', delete=False) as stream:
            stream.write(_json(receipt))
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        try:
            os.replace(temporary, ready)
        finally:
            temporary.unlink(missing_ok=True)
    print('CLEAN_OFFLINE_ACCEPTANCE_PASSED=' + str(path))
    print('PIN_MANIFEST_SHA256=' + manifest_sha)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'publish', 'verify', 'restore'))
    parser.add_argument('path')
    parser.add_argument('--identity', help='exact identity JSON, or @file')
    parser.add_argument('--base-image', help='trusted Task image@sha256:digest; build only')
    parser.add_argument('--source-root', default='/')
    parser.add_argument('--install-debs', action='store_true')
    args = parser.parse_args()
    if args.command == 'build' and not args.base_image:
        parser.error('build requires --base-image')
    if args.command != 'build' and not args.identity:
        parser.error('this command requires --identity')
    try:
        if args.command == 'build':
            build_bundle(args.path, args.base_image)
            return 0
        identity = json.loads(Path(args.identity[1:]).read_text() if args.identity.startswith('@') else args.identity)
        if args.command == 'publish':
            print(publish_bundle(args.source_root, args.path, identity))
        elif args.command == 'verify':
            print(verify_bundle(args.path, identity)['key'])
        else:
            actual = platform.freedesktop_os_release()
            if (actual['ID'], actual['VERSION_ID'], platform.machine()) != (identity['os_id'], identity['os_version'], identity['architecture']):
                raise CacheMiss('container platform mismatch before restore')
            manifest = restore_bundle(args.path, identity)
            if args.install_debs:
                # dpkg does not fetch missing dependencies: incomplete closure fails.
                install_manifest_debs(manifest)
            offline_check(identity)
            print('dependencies ready; no task tests loaded')
    except (CacheMiss, subprocess.CalledProcessError, OSError, ValueError) as exc:
        print('CACHE_MISS: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
