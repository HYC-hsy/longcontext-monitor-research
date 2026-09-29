"""Authorized serial admission/health monitoring only; never advises the Agents."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from launch_core4 import HERE, ROOT, BATCH, CASES


def main():
    parser = argparse.ArgumentParser()
    for name in ('authorization', 'profiles', 'supervisor-source', 'output-root', 'operator-log-root'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    out, logs = Path(args.output_root).resolve(), Path(args.operator_log_root).resolve()
    if out.exists():
        raise RuntimeError('formal panel output already exists; no repeat admission')
    logs.mkdir(parents=True, exist_ok=True)
    events = []
    def event(kind, **data):
        item = dict(time=time.time(), kind=kind, **data)
        events.append(item)
        (logs / 'serial_status.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
        print(json.dumps(item), flush=True)
    prepared = json.loads((HERE / 'environment_preparation.json').read_text())
    for record, (task, run) in CASES.items():
        if record == 'ratatui-m1' and not prepared['ratatui_ready']:
            event('NOT_STARTED_ENVIRONMENT_BLOCKED', record=record, run_id=run,
                reason='Fixed Cargo 1.82 cannot parse time-core 0.1.8 edition2024 from original Cargo.lock; no lockfile or toolchain change authorized.')
            continue
        if (out / 'archive_pause.json').exists():
            event('PANEL_PAUSED_ARCHIVE_FAILURE', record=record)
            return
        python = ROOT / 'bench_runtime/m2/host-env/python.exe' if record == 'sphinx-m1' else Path(sys.executable)
        cmd = [str(python), '-X', 'utf8', str(HERE / 'launch_core4.py'), '--batch-id', BATCH,
            '--record', record, '--run-id', run, '--supervisor-source', args.supervisor_source,
            '--output-root', str(out), '--execute', '--authorization', args.authorization,
            '--profiles', args.profiles]
        event('RECORD_START', record=record, task_id=task, run_id=run, command=cmd)
        with (logs / (record + '.stdout.log')).open('wb') as stdout, (logs / (record + '.stderr.log')).open('wb') as stderr:
            process = subprocess.Popen(cmd, cwd=ROOT, stdout=stdout, stderr=stderr)
            event('PROCESS_STARTED', record=record, pid=process.pid)
            last = 0
            while process.poll() is None:
                time.sleep(10)
                if time.time() - last < 60:
                    continue
                last = time.time()
                private = list((out / record).rglob('monitor_private/audit/progress.jsonl'))
                adapters = list((out / record).rglob('pilot_final_adapter.json'))
                if adapters:
                    actual = json.loads(adapters[0].read_text())
                    if (actual['max_turns'] != 300 or not actual['monitor_enabled']
                            or actual['llm_config_name'] != 'native_claude_cc_vibe_opus48'
                            or actual['monitor_config'] != 'claude_monitor_opus48'):
                        event('COMMON_IDENTITY_ANOMALY', record=record, actual=actual)
                        # No researcher steering / retry. Existing task timeout remains in effect.
                        return
                    configs = list((out / record / 'formal/jobs' / run).glob('*/config.json'))
                    if configs:
                        cfg = json.loads(configs[0].read_text())['agent']['kwargs']
                        if cfg.get('run_id') != run or cfg.get('max_turns') != 300:
                            event('COMMON_FINAL_PARAMETER_ANOMALY', record=record)
                            return
                # Absence is recorded while initialization is in flight; once Task
                # results exist, missing audit cannot be deferred until deletion.
                task_events = list((out / record).rglob('task_evidence/public_events.jsonl'))
                if any(p.stat().st_size > 0 for p in task_events) and not private:
                    event('PANEL_PAUSED_LIVE_ARCHIVE_MISSING', record=record)
                    return
                event('READ_ONLY_HEALTH', record=record, monitor_progress=[dict(path=str(p), bytes=p.stat().st_size) for p in private],
                    adapter_receipts=[str(p) for p in adapters])
        event('LAUNCHER_EXIT', record=record, code=process.returncode)
        if process.returncode or (out / 'archive_pause.json').exists():
            event('PANEL_PAUSED_EXECUTION_ERROR', record=record)
            return
        result_path = out / record / 'launch_result.json'
        if not result_path.is_file():
            event('PANEL_PAUSED_MISSING_RESULT', record=record)
            return
        if record == 'sphinx-m1':
            receipts = list((out / record / 'claw_swe').rglob('archive_before_cleanup.json'))
        else:
            receipts = list((out / record / 'formal/jobs').rglob('pilot_archive_receipt.json'))
            proofs = list((out / record / 'formal/runs').rglob('manifest.json'))
            if len(proofs) != 1:
                event('PANEL_PAUSED_MISSING_PROOF', record=record)
                return
            proof = json.loads(proofs[0].read_text())
            models = proof.get('trace', {}).get('observed_models', [])
            errors = proof.get('validation_errors', [])
            if not models or any(m != 'claude-opus-4-8' for m in models) or proof.get('agent_outputs', {}).get('all_fatal_infrastructure_error_only'):
                event('PANEL_PAUSED_MODEL_OR_TRANSPORT', record=record, models=models, errors=errors)
                return
            fatal = ('identity mismatch', 'metadata is not linked', 'provider/api error', 'api/infrastructure error')
            if any(any(term in str(e).lower() for term in fatal) for e in errors):
                event('PANEL_PAUSED_EXECUTION_ANOMALY', record=record, errors=errors)
                return
        if not receipts:
            event('PANEL_PAUSED_MISSING_ARCHIVE_RECEIPT', record=record)
            return
        event('RECORD_TERMINATED_ARCHIVE_PRESENT', record=record, receipts=[str(p) for p in receipts],
            result=json.loads(result_path.read_text()))
    event('PANEL_TERMINATED_STOP_NO_ADDITIONAL_RECORDS')


if __name__ == '__main__':
    main()
