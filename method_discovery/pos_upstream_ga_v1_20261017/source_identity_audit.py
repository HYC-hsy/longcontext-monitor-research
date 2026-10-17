"""Read-only Git/blob/worktree/bundle byte comparison for a retained run."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

from .single_manifest import SOURCE_FILES


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def compare(checkout: Path, commit: str, bundle: Path):
    rows = []
    for name in SOURCE_FILES:
        found = subprocess.run(['git', 'cat-file', 'blob', f'{commit}:{name}'],
            cwd=checkout, capture_output=True)
        if found.returncode:
            continue
        blob = found.stdout
        worktree = (checkout / name).read_bytes()
        staged = bundle / 'source' / Path(name).name
        if not staged.is_file():
            continue
        actual = staged.read_bytes()
        normalized = actual.replace(b'\r\n', b'\n')
        diff = list(difflib.unified_diff(
            blob.decode('utf-8', 'replace').splitlines(),
            normalized.decode('utf-8', 'replace').splitlines(),
            fromfile='git_blob', tofile='bundle_normalized', lineterm=''))
        rows.append({'path': name, 'git_blob_sha256': sha(blob),
            'worktree_sha256': sha(worktree), 'bundle_sha256': sha(actual),
            'git_blob_bytes': len(blob), 'worktree_bytes': len(worktree),
            'bundle_bytes': len(actual), 'bundle_crlf_count': actual.count(b'\r\n'),
            'bundle_lf_count': actual.count(b'\n'),
            'bundle_equals_worktree': actual == worktree,
            'bundle_equals_blob_after_crlf_normalization': normalized == blob,
            'normalized_content_diff': diff[:100]})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = compare(args.checkout, args.commit, args.bundle)
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'compared': len(rows), 'content_differences':
        [row['path'] for row in rows if row['normalized_content_diff']]},
        ensure_ascii=False))


if __name__ == '__main__':
    main()
