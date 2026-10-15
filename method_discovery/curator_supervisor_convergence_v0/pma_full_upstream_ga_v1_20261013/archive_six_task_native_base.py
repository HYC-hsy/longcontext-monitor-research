"""Copy allowlisted zero-model fixture evidence into a fresh public audit tree."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


FIXTURES = ('01', '02', '03', '04', '07', '08', '09', '10', '11',
            '12', '13', '14', '15', '16')
DENY = (b'sk-ant-', b'authorization: bearer ', b'"apikey":',
        b'"api_key":', b'"headers": {"authorization"')


def _copy(source: Path, destination: Path, inventory: list[dict]) -> None:
    if not source.is_file() or source.is_symlink() or source.stat().st_size > 5_000_000:
        raise RuntimeError(f'unsafe or missing fixture file: {source}')
    raw = source.read_bytes()
    if any(needle in raw.lower() for needle in DENY):
        raise RuntimeError(f'credential-like fixture content: {source}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
        raise RuntimeError('fixture evidence readback mismatch')
    source_run = next(parent for parent in source.parents
                      if parent.name.startswith(('pma-native-shared-fixture-',
                                                 'pma-v2-controller-',
                                                 'pma-two-task-v3-fixture-')))
    checkout = Path(__file__).resolve().parents[3]
    inventory.append({'path': destination.relative_to(checkout).as_posix(),
                      'bytes': len(raw), 'sha256': digest,
                      'source_fixture': source_run.name,
                      'source_relative': source.relative_to(source_run).as_posix()})


def archive(source_parent: Path, target: Path,
            controller_root: Path | None = None) -> dict:
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    inventory = []
    for number in FIXTURES:
        run = source_parent / f'pma-native-shared-fixture-20261014-{number}'
        for source in (run / 'archive').rglob('*'):
            if source.is_file():
                _copy(source, target / 'fixtures' / number / 'archive' /
                      source.relative_to(run / 'archive'), inventory)
        if number == '02':
            for source in (run / 'host_private/archive').rglob('*'):
                if source.is_file():
                    _copy(source, target / 'fixtures' / number / 'pma_private' /
                          source.relative_to(run / 'host_private/archive'), inventory)
        for source in (run / 'jobs').rglob('result.json'):
            if source.parent == run / 'jobs' / f'native-shared-fixture-20261014-{number}':
                continue
            _copy(source, target / 'fixtures' / number / 'trial_result.json', inventory)
        for source in (run / 'jobs').rglob('reward.txt'):
            _copy(source, target / 'fixtures' / number / 'reward.txt', inventory)
    if controller_root is not None:
        sources = [controller_root / name for name in
                   ('batch.json', 'controller.stdout.txt', 'controller.stderr.txt',
                    'run-1/control/sidecar_stopped.json')]
        sources += list((controller_root / 'run-1/archive').rglob('*'))
        sources += list((controller_root / 'run-1/jobs').rglob('result.json'))
        for source in sources:
            if source.is_file():
                _copy(source, target / 'controller_entry' /
                      source.relative_to(controller_root), inventory)
    inventory.sort(key=lambda row: row['path'])
    result = {'schema': 'pma-ga-native-base-evidence-v1',
              'fixture_runs': list(FIXTURES), 'files': inventory}
    (target / 'FILE_HASHES.json').write_text(json.dumps(result, indent=2),
                                             encoding='utf-8')
    return {'fixtures': len(FIXTURES), 'files': len(inventory),
            'file_index_sha256': hashlib.sha256(
                (target / 'FILE_HASHES.json').read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-parent', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--controller-root', type=Path)
    args = parser.parse_args()
    print(json.dumps(archive(args.source_parent.resolve(strict=True),
                             args.output.resolve(strict=False),
                             args.controller_root.resolve(strict=True)
                             if args.controller_root else None)))


if __name__ == '__main__':
    main()
