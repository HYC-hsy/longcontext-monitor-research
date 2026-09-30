"""Research-side serial admission for preregistered Stage 1, with no model steering."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNS = [
    ('cprr-real-dev-pilot-20260930-01', 'm1'),
    ('cprr-real-dev-pilot-20260930-02', 'cprr'),
    ('cprr-real-dev-pilot-20260930-03', 'cprr'),
    ('cprr-real-dev-pilot-20260930-04', 'm1'),
]
SOURCES = {'m1': r'E:\longcontext-m1-746a695',
           'cprr': r'E:\longcontext-cprr-746a695'}
HASHES = {'m1': '762e7ae7b73a9b19fe1af458745407f76287b53a2529dfaba546008e0c3cb656',
          'cprr': 'd47ac2b8e36e1c616b52f230526acfbac2e925e5ea6edd5b777dea256993720b'}


def verify(out, run, arm):
    job = out / 'jobs' / run
    trials = [p for p in job.iterdir() if p.is_dir()]
    if len(trials) != 1:
        raise RuntimeError(f'{run}: expected one trial, found {len(trials)}')
    trial = trials[0]
    cfg = json.loads((trial / 'config.json').read_text())['agent']['kwargs']
    expected_turns = 500 if run.endswith(('-01', '-02')) else 300
    if (cfg.get('run_id') != run or cfg.get('max_turns') != expected_turns
            or cfg.get('ga_source_sha256') != HASHES[arm]
            or cfg.get('llm_config_name') != 'native_claude_cc_vibe_opus48'
            or cfg.get('monitor_config') != 'claude_monitor_opus48'
            or cfg.get('monitor_enabled') is not True):
        raise RuntimeError(f'{run}: final adapter identity mismatch')
    monitor = trial / 'agent/monitor/monitor_private'
    for rel in ('working.md', 'audit/dialogue.jsonl', 'audit/progress.jsonl',
                'audit/provider_history.json', 'audit/request_attempts.jsonl'):
        if not (monitor / rel).is_file():
            raise RuntimeError(f'{run}: Supervisor original missing: {rel}')
    if not (trial / 'agent/monitor/runtime_receipts.jsonl').is_file():
        raise RuntimeError(f'{run}: runtime receipts missing')
    proofs = list((out / 'runs' / run).glob('manifest.json'))
    if len(proofs) != 1:
        raise RuntimeError(f'{run}: native proof manifest missing')
    proof = json.loads(proofs[0].read_text())
    if proof.get('agent_outputs', {}).get('all_fatal_infrastructure_error_only'):
        raise RuntimeError(f'{run}: fatal infrastructure agent output')
    return {'run_id': run, 'trial': str(trial), 'proof': str(proofs[0]),
            'native_rewards': proof.get('rewards'), 'trial_outcome': proof.get('trial_outcome')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--first-pid', required=True, type=int)
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args()
    out = Path(args.output_root).resolve()
    log = out / 'serial_stage1_status.jsonl'

    def emit(kind, **data):
        row = {'time': time.time(), 'kind': kind, **data}
        with log.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row) + '\n')
        print(json.dumps(row), flush=True)

    emit('WAIT_FIRST_RECORD', pid=args.first_pid)
    while psutil.pid_exists(args.first_pid):
        time.sleep(30)
    first_result = out / 'source_inputs' / RUNS[0][0] / 'result.json'
    if not first_result.is_file():
        emit('STOP_FIRST_RECORD_NO_RESULT')
        return 1
    try:
        emit('RECORD_ARCHIVED', **verify(out, *RUNS[0]))
    except Exception as error:
        emit('STOP_ARCHIVE_OR_IDENTITY', run_id=RUNS[0][0], error=str(error))
        return 1
    for run, arm in RUNS[1:]:
        if (out / 'archive_pause.json').exists():
            emit('STOP_ARCHIVE_PAUSE', next_run=run)
            return 1
        command = [sys.executable, '-X', 'utf8', str(HERE / 'launch_roadmap.py'),
                   '--run-id', run, '--source', SOURCES[arm], '--output-root', str(out), '--execute']
        emit('RECORD_START', run_id=run, arm=arm)
        with (out / (run + '.stdout.log')).open('wb') as stdout, (out / (run + '.stderr.log')).open('wb') as stderr:
            process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr)
            code = process.wait()
        emit('RECORD_EXIT', run_id=run, returncode=code)
        if code:
            emit('STOP_EXECUTION_ERROR', run_id=run)
            return 1
        try:
            emit('RECORD_ARCHIVED', **verify(out, run, arm))
        except Exception as error:
            emit('STOP_ARCHIVE_OR_IDENTITY', run_id=run, error=str(error))
            return 1
    emit('STAGE1_FINISHED_GATE_PENDING')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
