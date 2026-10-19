"""Read-back verification of derived public files and exact committed blobs."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    result = {}
    for name in ('raw_native_shared_v1', 'raw_native_shared_v2',
                 'raw_native_shared_v3', 'raw_offline_v4',
                 'raw_native_shared_v4', 'raw_profile_process_v1'):
        base = BASE / name
        index = json.loads((base / 'FILE_HASHES.json').read_text(encoding='utf-8'))
        count = 0
        for item in index['files']:
            relative = item.get('path', item.get('public_path',
                                item.get('public_file')))
            target = (base / relative).resolve(strict=True)
            if not target.is_relative_to(base):
                raise RuntimeError('evidence path escapes published directory')
            data = target.read_bytes()
            expected_hash = item.get('sha256', item.get('public_sha256'))
            expected_bytes = item.get('bytes', item.get('public_bytes'))
            if len(data) != expected_bytes or sha(data) != expected_hash:
                raise RuntimeError('published member bytes differ: ' + str(target))
            blob = subprocess.run(['git', 'show', 'HEAD:' +
                target.relative_to(ROOT).as_posix()], cwd=ROOT,
                check=True, capture_output=True).stdout
            if blob != data:
                raise RuntimeError('Git blob differs from public member: ' + str(target))
            count += 1
        result[name] = count
    print(json.dumps({'status': 'pass', 'exact_public_and_git_bytes': True,
                      'files_per_directory': result}, sort_keys=True))


if __name__ == '__main__':
    main()
