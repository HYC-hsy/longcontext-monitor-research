"""Persist the targeted no-network D1/V1 regression output verbatim."""

from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import io
from pathlib import Path
import sys
import unittest

import method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.offline_launcher as offline_launcher


MODULES = (
    'test_decision_phase2_live', 'test_decision_reminder_agent',
    'test_episode', 'test_live_wiring', 'test_single_run_offline',
)
PACKAGE = 'method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013'


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit('usage: python -m decision_phase2_test_gate NEW_OUTPUT_FILE')
    target = Path(sys.argv[1])
    if target.exists():
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    sys.modules['offline_launcher'] = offline_launcher
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromNames(
        [f'{PACKAGE}.{name}' for name in MODULES])
    with redirect_stdout(stream), redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    raw = ('COMMAND: python -m decision_phase2_test_gate ' + str(target) + '\n'
           'MODULES: ' + ', '.join(MODULES) + '\n'
           'REAL PROVIDER/TASK/NATIVE EVALUATOR CALLS: 0\n\n' + stream.getvalue())
    target.write_text(raw, encoding='utf-8')
    print(f'ran={result.testsRun} failures={len(result.failures)} '
          f'errors={len(result.errors)} skipped={len(result.skipped)} '
          f'output={target}')
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
