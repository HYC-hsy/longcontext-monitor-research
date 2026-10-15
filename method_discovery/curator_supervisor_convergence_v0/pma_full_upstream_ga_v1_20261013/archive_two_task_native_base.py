"""Allowlisted, credential-screened raw evidence for the V3 zero-model gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from .archive_six_task_native_base import _copy


def archive(source: Path, target: Path) -> dict:
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    inventory: list[dict] = []
    for name in ('manifest.json', 'batch.json', 'controller.stdout.txt',
                 'controller.stderr.txt', 'fake_authorization_removed.json'):
        _copy(source / name, target / name, inventory)
    for number in range(1, 5):
        run = source / f'run-{number}'
        for relative in ('archive', 'host_private/archive'):
            for item in (run / relative).rglob('*'):
                if item.is_file():
                    _copy(item, target / f'run-{number}' / relative /
                          item.relative_to(run / relative), inventory)
        for item in (run / 'jobs').rglob('result.json'):
            _copy(item, target / f'run-{number}/jobs' /
                  item.relative_to(run / 'jobs'), inventory)
        for item in (run / 'jobs').rglob('research_events.jsonl'):
            _copy(item, target / f'run-{number}/jobs' /
                  item.relative_to(run / 'jobs'), inventory)
    inventory.sort(key=lambda row: row['path'])
    index = {'schema': 'pma-ga-two-task-zero-model-evidence-v1',
             'source_fixture': str(source), 'files': inventory}
    (target / 'FILE_HASHES.json').write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding='utf-8')
    with zipfile.ZipFile(target / 'raw_trajectories.zip', 'w',
                         compression=zipfile.ZIP_DEFLATED) as bundle:
        for row in inventory:
            path = Path(__file__).resolve().parents[3] / row['path']
            bundle.write(path, arcname=path.relative_to(target).as_posix())
    return {'files': len(inventory),
            'index_sha256': hashlib.sha256(
                (target / 'FILE_HASHES.json').read_bytes()).hexdigest(),
            'zip_sha256': hashlib.sha256(
                (target / 'raw_trajectories.zip').read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(archive(args.source.resolve(strict=True),
                             args.output.resolve(strict=False))))


if __name__ == '__main__':
    main()
