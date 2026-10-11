"""Create one uploadable text audit bundle and hash every delivered file."""

import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CODE = '8cfc4ef2aac99c2378d98a0489fc0cad45511573'


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(data)
    return value.hexdigest()


def main():
    original = HERE / 'RAW_FILE_MANIFEST.json'
    copied = json.loads(original.read_text(encoding='utf-8'))['copied']
    for row in copied:
        path = HERE / row['path']
        if path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise RuntimeError(f'Raw copied evidence changed: {row["path"]}')
    with zipfile.ZipFile(HERE / 'RAW_TRAJECTORIES.zip') as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Trajectory ZIP CRC failure')
    diff = subprocess.run(['git', 'show', '--format=fuller', CODE, '--',
        'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/pilot_profile.py',
        'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/test_pilot_profile.py',
        'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/test_pilot_entry.py'],
        cwd=REPO, capture_output=True, text=True, check=True).stdout
    sections = [('BASE AUDIT PACKAGE', HERE / 'AUDIT_PACKAGE.txt'),
                ('VALIDATION AND LIMITS', HERE / 'VALIDATION_AND_LIMITS.txt'),
                ('RAW FILE MANIFEST', HERE / 'RAW_FILE_MANIFEST.json')]
    for arm in ('fyne_t', 'fyne_s', 'kitex_s', 'kitex_t'):
        sections.append((f'{arm.upper()} FINAL WORKSPACE MANIFEST',
                         HERE / 'arms' / arm / 'FINAL_WORKSPACE_MANIFEST.json'))
    content = 'FULL UPLOADABLE TEXT AUDIT PACKAGE — FYNE/KITEX PILOT BATCH 2\n'
    content += 'Credential-free mechanical evidence; raw binary products are indexed separately.\n'
    content += '\n===== RUN CODE DIFF =====\n' + diff
    for label, path in sections:
        content += f'\n===== {label} ({path.relative_to(HERE).as_posix()}) =====\n'
        content += path.read_text(encoding='utf-8')
    complete = HERE / 'AUDIT_PACKAGE_COMPLETE.txt'
    if complete.exists():
        raise FileExistsError(complete)
    complete.write_text(content, encoding='utf-8')
    files = []
    for path in sorted(HERE.rglob('*')):
        if path.is_file() and path.name not in {'DELIVERY_FILE_MANIFEST.json', 'FINAL_DELIVERY_IDENTITY.json'}:
            files.append({'path': path.relative_to(HERE).as_posix(),
                          'bytes': path.stat().st_size, 'sha256': sha(path)})
    manifest = HERE / 'DELIVERY_FILE_MANIFEST.json'
    if manifest.exists():
        raise FileExistsError(manifest)
    manifest.write_text(json.dumps({'schema': 'pilot-batch2-delivery-files-v1',
                                    'files': files}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    identity = {'audit_package_complete_sha256': sha(complete),
                'delivery_file_manifest_sha256': sha(manifest),
                'raw_file_manifest_sha256': sha(original),
                'raw_trajectories_zip_sha256': sha(HERE / 'RAW_TRAJECTORIES.zip'),
                'run_code_commit': CODE,
                'delivered_file_count_excluding_identity_and_manifest': len(files),
                'largest_delivered_file_bytes': max(row['bytes'] for row in files)}
    (HERE / 'FINAL_DELIVERY_IDENTITY.json').write_text(
        json.dumps(identity, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(identity, indent=2))


if __name__ == '__main__':
    main()
