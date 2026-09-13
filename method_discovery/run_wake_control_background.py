"""One approved run: isolated API check, then experiment, no automatic reruns."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'method_discovery/artifacts/wake_control_20260913'
MANIFEST = OUT / 'fyne_r1_manifest.json'


def state(stage, **fields):
    record = dict(stage=stage, timestamp=time.time(), **fields)
    with (OUT / 'background_status.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record) + '\n')
    print(json.dumps(record), flush=True)


def main():
    lock = OUT / 'background_started.json'
    with lock.open('x', encoding='utf-8') as stream:
        json.dump({'started_at': time.time()}, stream)
    run = json.loads(MANIFEST.read_text(encoding='utf-8'))['runs'][0]
    state('connectivity_check', run_id=run['run_id'])
    with (OUT / 'connectivity.log').open('w', encoding='utf-8') as log:
        checked = subprocess.run([sys.executable, '-m', 'scripts.probe_isolated_models',
            '--output', str(OUT / 'api_preflight')], cwd=ROOT / 'long_context_bench',
            stdout=log, stderr=subprocess.STDOUT)
    if checked.returncode:
        state('stopped_before_task', reason='connectivity_check_failed', returncode=checked.returncode)
        return checked.returncode
    with (OUT / 'runner.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(run['argv'], cwd=run['cwd'], stdout=log, stderr=subprocess.STDOUT)
        state('runner_started', run_id=run['run_id'], pid=process.pid)
        code = process.wait()
    state('runner_finished', returncode=code, run_id=run['run_id'])
    return code


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        state('background_failed', error_type=type(exc).__name__, error=str(exc))
        raise
