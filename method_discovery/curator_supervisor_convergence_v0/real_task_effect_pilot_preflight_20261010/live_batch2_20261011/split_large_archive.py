"""Split one oversized lossless checkpoint archive for remote Git delivery."""

import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parent
CONTROL = Path(r'E:\pilot_live_batch2_20261011_8cfc4ef2')
RELATIVE = 'arms/fyne_s/monitor/audit/live_checkpoints.tar.gz'
SOURCE = ROOT / RELATIVE
LOCAL = CONTROL / 'fyne_s_live_checkpoints.tar.gz'
MANIFEST = ROOT / 'RAW_FILE_MANIFEST.json'
CHUNK = 64 * 1024 * 1024


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(data)
    return value.hexdigest()


def main():
    if not SOURCE.is_file() or LOCAL.exists():
        raise RuntimeError('Oversized source absent or local destination already occupied')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    entries = [entry for entry in manifest['copied'] if entry['path'] == RELATIVE]
    if len(entries) != 1 or digest(SOURCE) != entries[0]['sha256']:
        raise RuntimeError('Original archive identity mismatch')
    parts = []
    with SOURCE.open('rb') as stream:
        index = 0
        while data := stream.read(CHUNK):
            path = SOURCE.with_name(f'{SOURCE.name}.part{index:03d}')
            if path.exists():
                raise FileExistsError(path)
            with path.open('xb') as target:
                target.write(data)
            parts.append({'path': path.relative_to(ROOT).as_posix(), 'bytes': len(data),
                          'sha256': digest(path), 'source': str(SOURCE),
                          'transformation': 'contiguous 64-MiB segment'})
            index += 1
    assembled = hashlib.sha256()
    length = 0
    for entry in parts:
        part = ROOT / entry['path']
        if digest(part) != entry['sha256']:
            raise RuntimeError('Checkpoint part identity mismatch')
        with part.open('rb') as stream:
            for data in iter(lambda: stream.read(1024 * 1024), b''):
                assembled.update(data)
                length += len(data)
    if assembled.hexdigest() != entries[0]['sha256'] or length != entries[0]['bytes']:
        raise RuntimeError('Reassembled checkpoint archive identity mismatch')
    shutil.move(str(SOURCE), str(LOCAL))
    if digest(LOCAL) != entries[0]['sha256']:
        raise RuntimeError('Moved local checkpoint archive identity mismatch')
    manifest['copied'] = [entry for entry in manifest['copied'] if entry['path'] != RELATIVE] + parts
    manifest.setdefault('reassembly', []).append({
        'path': RELATIVE, 'sha256': entries[0]['sha256'], 'bytes': entries[0]['bytes'],
        'parts': [entry['path'] for entry in parts], 'local_copy': str(LOCAL),
    })
    temporary = MANIFEST.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(MANIFEST)
    print(json.dumps({'parts': len(parts), 'reassembled_sha256': assembled.hexdigest(),
                      'local_copy': str(LOCAL)}))


if __name__ == '__main__':
    main()
