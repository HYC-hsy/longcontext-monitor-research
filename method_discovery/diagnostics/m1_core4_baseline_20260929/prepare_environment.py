"""Authorized dependency/environment preparation; no Agent or verifier calls."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
RAT = 'sha256:6f9da0a2c21293e8e0d2bac70947260da9edd9e3de0bcb09af3008218bbcc18d'
SPHINX = 'sha256:77f476927410992943a8d2744aea86b3e0c50d8773b61e56ebba9dd0fd4b9db1'


def run(args, timeout=300):
    result = subprocess.run(args, capture_output=True, encoding='utf-8', errors='replace', timeout=timeout)
    return dict(command=args, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)


def main():
    output = HERE / 'environment_preparation.json'
    if output.exists():
        raise RuntimeError('existing preparation receipt: do not overwrite')
    steps = []
    def step(args, timeout=300):
        receipt = run(args, timeout)
        steps.append(receipt)
        output.write_text(json.dumps(dict(steps=steps, real_model_calls=0), indent=2), encoding='utf-8')
        print(json.dumps(receipt), flush=True)
        return receipt
    # Only public test loading, no behavior assertions / hidden evaluation.
    sphinx = step(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', '/bin/bash', SPHINX,
        '-lc', 'cd /testbed && /opt/miniconda3/envs/testbed/bin/python -c '
        "'import sys,pytest,docutils; print(sys.executable); print(pytest.__version__,pytest.__file__); print(docutils.__version__,docutils.__file__)' "
        '&& /opt/miniconda3/envs/testbed/bin/python -m pytest --collect-only -q tests/test_util.py'], 180)
    # A fresh preparation container may access registries. No Task source edit.
    name = 'm1-core4-ratatui-cache-preparation-v2'
    created = step(['docker', 'create', '--name', name, '--entrypoint', '/bin/bash', RAT, '-lc', 'sleep infinity'])
    if created['returncode']:
        raise RuntimeError('preparation container creation failed')
    step(['docker', 'start', name])
    initial = step(['docker', 'exec', name, 'bash', '-lc',
        'export PATH=/usr/local/cargo/bin:$PATH; cd /app && git rev-parse HEAD && git status --porcelain && sha256sum Cargo.toml Cargo.lock && '
        'grep -A 4 \'name = "unicode-segmentation"\' Cargo.lock && '
        'cargo metadata --offline --locked --format-version 1 >/tmp/initial_metadata.json'])
    # Exact version from the public Dockerfile/environment dependency contract.
    fetch = step(['docker', 'exec', name, 'bash', '-lc',
        'export PATH=/usr/local/cargo/bin:$PATH; mkdir -p /tmp/core4-cache-fetch/src && '
        "printf '[package]\nname=\"core4_cache_fetch\"\nversion=\"0.0.0\"\nedition=\"2021\"\n[dependencies]\nunicode-segmentation=\"=1.12.0\"\n' > /tmp/core4-cache-fetch/Cargo.toml && "
        "printf 'fn main() {}\n' > /tmp/core4-cache-fetch/src/main.rs && "
        'mv /root/.cargo/config.toml /tmp/original_cargo_config.toml && '
        'cd /tmp/core4-cache-fetch && cargo fetch && '
        'cd /app && cargo fetch --locked'], 600)
    # Preserve the original registry configuration and remove preparation-only artifacts.
    step(['docker', 'exec', name, 'bash', '-lc',
        'test ! -f /tmp/original_cargo_config.toml || mv /tmp/original_cargo_config.toml /root/.cargo/config.toml; '
        'cd /app; git status --porcelain; sha256sum Cargo.toml Cargo.lock; '
        'find /usr/local/cargo/registry/cache -type f -name "*.crate" -exec sha256sum {} +'])
    # Public package resolution/build check, disconnected from registries.
    network = json.loads(subprocess.check_output(['docker', 'inspect', name]))[0]['NetworkSettings']['Networks']
    for net in network:
        step(['docker', 'network', 'disconnect', net, name])
    check = step(['docker', 'exec', name, 'bash', '-lc',
        'export PATH=/usr/local/cargo/bin:$PATH; cd /app && cargo metadata --locked --offline --format-version 1 >/tmp/prepared_metadata.json '
        '&& cargo test --locked --offline --lib --no-run'], 600)
    # Commit only a cache layer by removing all build/preparation changes and verifying /app.
    clean = step(['docker', 'exec', name, 'bash', '-lc',
        'cd /app && git diff --exit-code && test -z "$(git status --porcelain)" && '
        'rm -rf /tmp/core4-cache-fetch /tmp/initial_metadata.json /tmp/prepared_metadata.json'])
    if fetch['returncode'] == check['returncode'] == clean['returncode'] == 0:
        committed = step(['docker', 'commit', name, 'm1-core4-ratatui-cache:20260929'])
        image = committed['stdout'].strip() if committed['returncode'] == 0 else None
    else:
        image = None
    result = dict(steps=steps, sphinx_loading_ready=sphinx['returncode'] == 0,
        ratatui_ready=image is not None, ratatui_parent=RAT, ratatui_image=image,
        source_registry='https://index.crates.io / https://static.crates.io',
        preparation_container=name, real_model_calls=0, evaluator_calls=0)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    # Keep preparation container for forensic inspection; never an Agent input.
    step(['docker', 'stop', name])
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
