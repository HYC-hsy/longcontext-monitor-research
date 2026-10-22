"""Pinned SQLite verifier dependency preparation, without running its tests.

Only the byte-identified original test.sh may be split. The suffix is copied
verbatim into the effective test script; this module never parses test claims.
"""

from __future__ import annotations

import hashlib


PROTOCOL = 'bootstrap_retry_v1'
TASK = 'sqlite-with-gcov'
ORIGINAL_SHA256 = '4770437ea96c3cc84684b4f99d55fb148fcac09f9ea1e8ef49de487716e6c334'
PREPARATION_PREFIX = (
    b'#!/bin/bash\n\n'
    b'# Install curl\napt-get update\napt-get install -y curl\n\n'
    b'# Install uv\ncurl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh\n\n'
    b'source $HOME/.local/bin/env\n\n'
)
TEST_BOUNDARY = b"# Check if we're in a valid working directory\n"
EFFECTIVE_HEADER = b'#!/bin/bash\nsource "$HOME/.local/bin/env"\nexport UV_OFFLINE=1\n\n'
PACKAGE_ARGUMENTS = '-p 3.13 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5'


class BootstrapFailed(RuntimeError):
    def __init__(self, stage: str, return_code: int | None, detail: str):
        self.stage, self.return_code = stage, return_code
        super().__init__(f'{stage}: {detail}')


def effective_script(original: bytes, *, task: str) -> bytes:
    if task != TASK or hashlib.sha256(original).hexdigest() != ORIGINAL_SHA256:
        raise BootstrapFailed('identity', None, 'unsupported original verifier bytes')
    if not original.startswith(PREPARATION_PREFIX):
        raise BootstrapFailed('boundary', None, 'pinned preparation prefix changed')
    suffix = original[len(PREPARATION_PREFIX):]
    if not suffix.startswith(TEST_BOUNDARY) or suffix.count(TEST_BOUNDARY) != 1:
        raise BootstrapFailed('boundary', None, 'pinned test boundary changed')
    return EFFECTIVE_HEADER + suffix


def commands() -> tuple[tuple[str, str], ...]:
    """Finite preparation only; the final commands load no task test file."""
    return (
        ('apt_update', 'apt-get -o Acquire::Retries=3 '
         '-o APT::Update::Error-Mode=any update'),
        ('apt_install', 'apt-get -o Acquire::Retries=3 install -y curl'),
        ('curl_version', 'command -v curl && curl --version'),
        ('uv_install', 'bash -o pipefail -c '
         "'curl -fLsS --retry 3 --retry-delay 2 "
         'https://astral.sh/uv/0.9.5/install.sh | sh\''),
        ('uv_version', '. "$HOME/.local/bin/env" && command -v uvx && uvx --version'),
        ('uv_digest', 'sha256sum "$HOME/.local/bin/uvx"'),
        ('dependency_versions', '. "$HOME/.local/bin/env" && '
         f"uvx {PACKAGE_ARGUMENTS} python -c 'import importlib.metadata as m; "
         'print(m.version("pytest")); print(m.version("pytest-json-ctrf"))\''),
        ('plugin_contract', '. "$HOME/.local/bin/env" && bash -o pipefail -c '
         f"'uvx {PACKAGE_ARGUMENTS} pytest --help | grep -F -- --ctrf'"),
    )


async def prepare(exec_command, record):
    """Execute each bounded stage once; APT/curl own their finite file retries."""
    for stage, command in commands():
        record({'stage': stage, 'status': 'started', 'command_class': stage})
        try:
            result = await exec_command(command=command, user='root', timeout_sec=600)
        except Exception as exc:
            record({'stage': stage, 'status': 'failed', 'error_type': type(exc).__name__})
            raise BootstrapFailed(stage, None, type(exc).__name__) from exc
        receipt = {'stage': stage, 'status': 'complete' if result.return_code == 0 else 'failed',
                   'return_code': result.return_code,
                   'stdout_sha256': hashlib.sha256((result.stdout or '').encode()).hexdigest(),
                   'stderr_sha256': hashlib.sha256((result.stderr or '').encode()).hexdigest(),
                   'stdout_excerpt': (result.stdout or '')[:500]}
        if result.return_code == 0 and stage == 'uv_version' and '0.9.5' not in (result.stdout or ''):
            receipt['status'] = 'failed'
            record(receipt)
            raise BootstrapFailed(stage, 0, 'uv version differs from pinned installer')
        if result.return_code == 0 and stage == 'dependency_versions' and (
                '8.4.1' not in (result.stdout or '') or '0.3.5' not in (result.stdout or '')):
            receipt['status'] = 'failed'
            record(receipt)
            raise BootstrapFailed(stage, 0, 'resolved Python dependency versions differ')
        record(receipt)
        if result.return_code:
            raise BootstrapFailed(stage, result.return_code, 'dependency command failed')
