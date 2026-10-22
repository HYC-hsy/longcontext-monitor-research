"""Conservative, versioned download preparation for native verifier scripts.

Only two byte-level dependency shapes are supported. Unknown scripts run as
original once; this module does not interpret assertions or scoring logic.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import shlex

from .evaluation_bootstrap import BootstrapFailed


PROTOCOL = 'download_retry_v1'
UV_INSTALLER = 'https://astral.sh/uv/0.9.5/install.sh'
_SAFE_PACKAGE = re.compile(r'[A-Za-z0-9_.+-]+(?:==[A-Za-z0-9_.+-]+)?\Z')
_UVX = re.compile(
    rb'(?m)^uvx \\\n  -p (3\.13) \\\n'
    rb'((?:  -w [A-Za-z0-9_.+\-]+==[A-Za-z0-9_.+\-]+ \\\n)+)'
    rb'  pytest --ctrf /logs/verifier/ctrf\.json ')


@dataclass(frozen=True)
class DownloadPlan:
    original_sha256: str
    effective: bytes
    coverage: str
    stages: tuple[tuple[str, str], ...]


def _uvx_warmup(original: bytes, retries: int) -> str | None:
    matches = list(_UVX.finditer(original))
    if len(matches) != 1:
        return None
    match = matches[0]
    wheels = re.findall(rb'  -w ([A-Za-z0-9_.+\-]+==[A-Za-z0-9_.+\-]+) \\\n',
                        match.group(2))
    if not wheels or not any(w.startswith(b'pytest==') for w in wheels):
        return None
    flags = ' '.join('-w ' + w.decode('ascii') for w in wheels)
    return (f'UV_HTTP_RETRIES={retries} uvx -p 3.13 {flags} '
            "python -c 'import sys; print(sys.version)'" )


def plan(original: bytes, max_attempts: int) -> DownloadPlan:
    if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
        raise ValueError('max_attempts must be an integer in 1..10')
    digest = hashlib.sha256(original).hexdigest()
    fallback = DownloadPlan(digest, original, 'uncovered_original_once', ())
    if not original.startswith(b'#!/bin/bash\n') or b'\r' in original:
        return fallback
    lines = original.splitlines(keepends=True)
    retries = max_attempts - 1
    # Shape 1: original APT package list, pinned uv installer, then one uvx
    # pytest command. The test and scoring suffix is byte-for-byte untouched.
    source = b'source $HOME/.local/bin/env\n'
    sources = [i for i, line in enumerate(lines) if line == source]
    if len(sources) == 1:
        boundary = sources[0]
        prefix = lines[1:boundary]
        apt_update = [x for x in prefix if x == b'apt-get update\n']
        installs = [x for x in prefix if re.fullmatch(
            rb'(?:DEBIAN_FRONTEND=noninteractive )?apt-get install -y [A-Za-z0-9.+\- ]+\n', x)]
        installer = f'curl -LsSf {UV_INSTALLER} | sh\n'.encode()
        other = [x for x in prefix if x.strip() and not x.lstrip().startswith(b'#') and
                 x not in apt_update and x not in installs and x != installer]
        warmup = _uvx_warmup(b''.join(lines[boundary + 1:]), retries)
        if (len(apt_update) == len(installs) == 1 and prefix.count(installer) == 1
                and not other and warmup):
            apt_install = installs[0].decode('ascii').strip().replace(
                'apt-get install', f'apt-get -o Acquire::Retries={retries} install', 1)
            stages = (
                ('apt_update', f'apt-get -o Acquire::Retries={retries} '
                 '-o APT::Update::Error-Mode=any update'),
                ('apt_install', apt_install),
                ('curl_version', 'command -v curl && curl --version'),
                ('uv_download', f'curl -fLsS --retry {retries} --retry-delay 2 '
                 f'-o /logs/verifier/{PROTOCOL}/installer.part {UV_INSTALLER} && '
                 f'test -s /logs/verifier/{PROTOCOL}/installer.part && '
                 f'mv /logs/verifier/{PROTOCOL}/installer.part '
                 f'/logs/verifier/{PROTOCOL}/installer.sh'),
                ('uv_installer_identity', f'sha256sum /logs/verifier/{PROTOCOL}/installer.sh'),
                ('uv_install', f'sh /logs/verifier/{PROTOCOL}/installer.sh'),
                ('uv_version', '. "$HOME/.local/bin/env" && command -v uvx && uvx --version'),
                ('uv_dependencies', '. "$HOME/.local/bin/env" && ' + warmup),
            )
            comments = b''.join(x for x in prefix if not x.strip() or
                                x.lstrip().startswith(b'#'))
            effective = (lines[0] + comments + b'export UV_HTTP_RETRIES=' +
                         str(retries).encode() + b'\n' + source +
                         b''.join(lines[boundary + 1:]))
            return DownloadPlan(digest, effective, 'apt_curl_uvx', stages)
    # Shape 2: one plain pip install before the first pytest invocation.
    pip_rows = [(i, x) for i, x in enumerate(lines) if x.startswith(b'pip install ')]
    if len(pip_rows) == 1:
        index, row = pip_rows[0]
        try:
            tokens = shlex.split(row.decode('ascii'))
        except (UnicodeError, ValueError):
            return fallback
        if (len(tokens) >= 3 and tokens[:2] == ['pip', 'install'] and
                all(t == '--break-system-packages' or _SAFE_PACKAGE.fullmatch(t)
                    for t in tokens[2:]) and
                b'pytest --ctrf /logs/verifier/ctrf.json ' in b''.join(lines[index + 1:]) and
                not any(b'apt-get ' in x or b'curl ' in x for x in lines[:index])):
            command = 'pip install --retries ' + str(max_attempts) + ' ' + ' '.join(tokens[2:])
            effective = b''.join(lines[:index] + lines[index + 1:])
            return DownloadPlan(digest, effective, 'pip',
                                (('pip_dependencies', command),))
    # Some task images already provide uvx. Prewarm only the recognized
    # dependency declaration; never alter its pytest invocation.
    warmup = _uvx_warmup(original, retries)
    if (warmup and not pip_rows and not any(
            b'apt-get ' in line or b'curl ' in line or line == source
            for line in lines)):
        effective = (lines[0] + b'export UV_HTTP_RETRIES=' + str(retries).encode() +
                     b'\n' + b''.join(lines[1:]))
        return DownloadPlan(digest, effective, 'uvx',
                            (('uv_version', 'command -v uvx && uvx --version'),
                             ('uv_dependencies', warmup)))
    return fallback


async def prepare(exec_command, record, stages: tuple[tuple[str, str], ...]):
    """Run each preparation stage once; tools own their bounded HTTP retries."""
    for name, command in stages:
        record({'stage': name, 'status': 'started', 'command_class': name})
        try:
            result = await exec_command(command=command, user='root', timeout_sec=600)
        except Exception as exc:
            record({'stage': name, 'status': 'failed', 'error_type': type(exc).__name__})
            raise BootstrapFailed(name, None, type(exc).__name__) from exc
        record({'stage': name, 'status': 'complete' if result.return_code == 0 else 'failed',
                'return_code': result.return_code,
                'stdout_sha256': hashlib.sha256((result.stdout or '').encode()).hexdigest(),
                'stderr_sha256': hashlib.sha256((result.stderr or '').encode()).hexdigest()})
        if result.return_code:
            raise BootstrapFailed(name, result.return_code, 'dependency preparation failed')
