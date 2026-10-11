"""Post-hoc evaluation of two exact archived artifacts; never starts an agent."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import time


ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'real_task_effect_pilot_preflight_20261010'
ARCHIVE = OLD / 'live_batch_20261011' / 'arms'
TASKS = Path('E:/LongContext/long_context_bench/.cache/m12_roadmap_tasks')
SPECS = {
    'kitex_s': {
        'archive': ARCHIVE / 'kitex_s/archive/pre_evaluation_app.tar.gz',
        'gzip_sha': '05a805653dc448228f82afd1c81eaff7a2b39d0f017761189c1c7d9d5906bb4a',
        'tar_sha': '5cefacd222d91056b316e06151566a6574e703f316978e370a8a2a48af78e3b4',
        'image': 'sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e',
        'task': TASKS / 'ktx-0.13.0-roadmap',
        'task_toml_sha': 'cd08b0c7d55b3059dba27c9970240e856aeb0a7ae301673675e3cc37d3f82a54',
        'tests_sha': '2c78b005db4c21e2b6e71117d553e3c1c00e43e978fa166533b864d00235ce1b',
        'test_sh_sha': 'f0a24e1ac883c65e04eec6a7ecc9e74ffb6214a7a0e1dcf7974eeb7bd3144324',
        'status': 'legal_agent_end=false; monitor_review_incomplete',
    },
    'fyne_s': {
        'archive': ARCHIVE / 'fyne_s/job/trial/agent/failure_workspace/workspace.tar.gz',
        'gzip_sha': '5738bf9e45d11c73b06626a3f64cf0e3013b81f510c1ddb571cab1fa6b70ab55',
        'tar_sha': '568a6464c6fdcfc34884beaa06c5b500b422afb0874f2ecfe4b866ab23495eee',
        'image': 'sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1',
        'task': TASKS / 'fyn-2.2.0-roadmap',
        'task_toml_sha': 'db81f4ee37e4f69e7ace0fa7b7cb6ab8b2cd3469463091b1bcf073da4237dd6d',
        'tests_sha': '9da32be9bee4f850d6c31d8bbdf463919477bbdc473437c09d9227c0cace6752',
        'test_sh_sha': '77637bf7eb621697259e7fad7428ed4cc578b17aef171fc76f44cf5474b8bda2',
        'status': 'best_effort_filesystem_copy_not_atomic; legal termination not certified',
    },
}


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def tree_sha(root):
    h = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_file():
            h.update(path.relative_to(root).as_posix().encode() + b'\0')
            h.update(path.read_bytes())
    return h.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def run(argv, *, timeout=60, input_stream=None):
    if input_stream is None:
        result = subprocess.run(argv, capture_output=True, timeout=timeout)
        return {'argv': argv, 'returncode': result.returncode,
                'stdout': result.stdout.decode('utf-8', 'replace'),
                'stderr': result.stderr.decode('utf-8', 'replace')}
    result = subprocess.run(argv, stdin=input_stream, capture_output=True, timeout=timeout)
    return {'argv': argv, 'returncode': result.returncode,
            'stdout': result.stdout.decode('utf-8', 'replace'),
            'stderr': result.stderr.decode('utf-8', 'replace')}


def preflight(arm, output):
    spec = SPECS[arm]
    output.mkdir(parents=True, exist_ok=False)
    report = {'arm': arm, 'source_status': spec['status'], 'source': str(spec['archive']),
              'input_gzip_sha': sha(spec['archive']), 'expected_gzip_sha': spec['gzip_sha']}
    write_json(output / 'preflight.json', report)
    if report['input_gzip_sha'] != spec['gzip_sha']:
        raise ValueError('Compressed archive SHA mismatch')
    tar_path = output / 'input.tar'
    with gzip.open(spec['archive'], 'rb') as source, open(tar_path, 'wb') as target:
        shutil.copyfileobj(source, target, 1024 * 1024)
    report['input_tar_sha'] = sha(tar_path)
    if report['input_tar_sha'] != spec['tar_sha']:
        write_json(output / 'preflight.json', report)
        raise ValueError('Uncompressed archive SHA mismatch')
    members = []
    with tarfile.open(tar_path, 'r:') as archive:
        for entry in archive:
            name = entry.name
            pure = PurePosixPath(name)
            if (pure.is_absolute() or '..' in pure.parts or '\\' in name or
                    not (entry.isfile() or entry.isdir())):
                raise ValueError('Unsafe tar member: ' + name)
            record = {'path': name, 'type': 'file' if entry.isfile() else 'directory',
                      'size': entry.size, 'mode': oct(entry.mode)}
            if entry.isfile():
                stream = archive.extractfile(entry)
                h = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(chunk)
                record['sha256'] = h.hexdigest()
            members.append(record)
    write_json(output / 'input_tar_manifest.json', members)
    report.update(member_count=len(members), file_count=sum(x['type'] == 'file' for x in members),
                  task_toml_sha=sha(spec['task'] / 'task.toml'),
                  tests_tree_sha=tree_sha(spec['task'] / 'tests'),
                  test_sh_sha=sha(spec['task'] / 'tests/test.sh'))
    for field, expected in [('task_toml_sha', 'task_toml_sha'), ('tests_tree_sha', 'tests_sha'),
                            ('test_sh_sha', 'test_sh_sha')]:
        if report[field] != spec[expected]:
            write_json(output / 'preflight.json', report)
            raise ValueError(field + ' mismatch')
    image = run(['docker', 'image', 'inspect', spec['image'], '--format', '{{json .}}'])
    if image['returncode'] != 0:
        raise RuntimeError('Pinned image unavailable')
    parsed = json.loads(image['stdout'])
    if parsed['Id'] != spec['image']:
        raise ValueError('Pinned image ID mismatch')
    report['image_id'] = parsed['Id']
    report['repo_digests'] = parsed.get('RepoDigests') or []
    report['safe_extraction'] = True
    write_json(output / 'preflight.json', report)
    return tar_path, report


def evaluate(arm, output, tar_path, report):
    spec = SPECS[arm]
    suffix = str(int(time.time())) + '-' + arm.replace('_', '-')
    volume, container = 'posthoc-s-' + suffix, 'posthoc-eval-' + suffix
    commands = []
    attempt = output / 'EVALUATOR_ATTEMPT_STARTED.json'
    try:
        commands.append(run(['docker', 'volume', 'create', volume]))
        if commands[-1]['returncode']:
            raise RuntimeError('Volume create failed')
        with open(tar_path, 'rb') as stream:
            commands.append(run(['docker', 'run', '--rm', '-i', '--network', 'none',
                                 '--mount', 'type=volume,source=' + volume + ',destination=/artifact',
                                 '--entrypoint', '/bin/sh', spec['image'], '-c',
                                 'cd /artifact && tar -xpf -'], timeout=180, input_stream=stream))
        if commands[-1]['returncode']:
            raise RuntimeError('Artifact extraction failed')
        commands.append(run(['docker', 'run', '-d', '--name', container, '--network', 'none',
                             '--cpus', '2', '--memory', '4096m', '--storage-opt', 'size=10G',
                             '--mount', 'type=volume,source=' + volume + ',destination=/app',
                             '--entrypoint', '/bin/sh', spec['image'], '-c', 'sleep infinity']))
        if commands[-1]['returncode']:
            raise RuntimeError('Evaluator container setup failed')
        commands.append(run(['docker', 'cp', str(spec['task'] / 'tests') + '/.',
                             container + ':/tests/'], timeout=180))
        if commands[-1]['returncode']:
            raise RuntimeError('Native tests staging failed')
        commands.append(run(['docker', 'exec', '-u', 'root', container, 'chmod', '+x', '/tests/test.sh']))
        if commands[-1]['returncode']:
            raise RuntimeError('Native test chmod failed')
        # The marker is written before the single allowed evaluator invocation.
        write_json(attempt, {'arm': arm, 'started_at_epoch': time.time(),
                             'command': '(/tests/test.sh) > /logs/verifier/test-stdout.txt 2>&1'})
        commands.append(run(['docker', 'exec', container, '/bin/sh', '-c',
                             'mkdir -p /logs/verifier && (/tests/test.sh) > /logs/verifier/test-stdout.txt 2>&1'],
                            timeout=1800))
        for path in ('/logs/verifier/test-stdout.txt', '/logs/verifier/reward.json',
                     '/logs/verifier/reward.txt'):
            dest = output / Path(path).name
            copied = run(['docker', 'cp', container + ':' + path, str(dest)], timeout=120)
            commands.append(copied)
        report['native_evaluator_started'] = True
        report['native_returncode'] = commands[-4]['returncode']
        report['native_reward_json'] = ((output / 'reward.json').read_text(encoding='utf-8')
                                        if (output / 'reward.json').exists() else None)
        report['native_reward_txt'] = ((output / 'reward.txt').read_text(encoding='utf-8')
                                       if (output / 'reward.txt').exists() else None)
    except Exception as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        commands.append(run(['docker', 'rm', '-f', container]))
        commands.append(run(['docker', 'volume', 'rm', volume]))
        commands.append(run(['docker', 'inspect', container]))
        commands.append(run(['docker', 'volume', 'inspect', volume]))
        report['cleanup_confirmed'] = (commands[-2]['returncode'] != 0 and
                                       'no such object' in commands[-2]['stderr'].lower() and
                                       commands[-1]['returncode'] != 0 and
                                       'no such volume' in commands[-1]['stderr'].lower())
        write_json(output / 'docker_commands_and_results.json', commands)
        write_json(output / 'evaluation_result.json', report)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('arm', choices=SPECS)
    parser.add_argument('--output', required=True)
    parser.add_argument('--evaluate', action='store_true')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    tar_path, report = preflight(args.arm, output)
    if args.evaluate:
        evaluate(args.arm, output, tar_path, report)


if __name__ == '__main__':
    main()
