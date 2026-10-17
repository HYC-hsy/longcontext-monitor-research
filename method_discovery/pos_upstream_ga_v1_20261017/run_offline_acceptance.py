"""Run selected deterministic tests and preserve their exact stdout/stderr bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
P = 'method_discovery/pos_upstream_ga_v1_20261017/'
H = ('method_discovery/curator_supervisor_convergence_v0/'
     'pma_full_upstream_ga_v1_20261013/')
TESTS = {'pos_core': P + 'test_offline.py',
         'pos_ga_seam': P + 'test_ga_seam.py',
         'legacy_single_run': H + 'test_single_run_offline.py',
         'legacy_live_wiring': H + 'test_live_wiring.py'}
LEGACY_SINGLE_METHODS = (
    'test_stream_projection_removes_private_delta_and_preserves_public',
    'test_preparation_and_run_receipts_are_distinct',
    'test_single_run_exit_code_uses_disposition_not_reward',
    'test_public_projection_removes_nested_hidden_thinking',
    'test_selection_subsets_repeats_and_identity',
    'test_single_binding_never_authorizes_changed_slot',
    'test_registered_wrapper_stops_but_task_service_survives',
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for name, script in TESTS.items():
        module = script[:-3].replace('/', '.')
        command = ([sys.executable, '-B', '-m', 'unittest'] +
                   ([module + '.SingleRunOfflineTests.' + method
                     for method in LEGACY_SINGLE_METHODS]
                    if name == 'legacy_single_run' else [module])
                   if script.startswith(H) else [sys.executable, '-B', script])
        run = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
        for stream, content in (('stdout', run.stdout), ('stderr', run.stderr)):
            (args.output / f'{name}.{stream}.txt').write_bytes(content)
        results.append({'name': name, 'command': command,
                        'exit_code': run.returncode,
                        'stdout_sha256': hashlib.sha256(run.stdout).hexdigest(),
                        'stderr_sha256': hashlib.sha256(run.stderr).hexdigest()})
    (args.output / 'results.json').write_text(json.dumps(results, indent=2) + '\n',
                                              encoding='utf-8', newline='\n')
    print(json.dumps(results))
    if any(row['exit_code'] for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
