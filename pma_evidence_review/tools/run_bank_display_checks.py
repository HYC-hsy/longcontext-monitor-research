"""Strict fake-client engineering checks; no semantic evaluation or live launch."""
import argparse
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ['PMA_TEST_STRICT_IMPORTS'] = '1'
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
from pma_evidence_review.tests import run_gate_regressions as runner
from pma_evidence_review.tools.run_p2_selection_checks import SUITES as OLD_SUITES

SUITES = OLD_SUITES + ('test_bank_display.py', 'test_bank_display_host.py',
                      'test_bank_display_boundaries.py', 'test_bank_display_prepare.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError('use a new local report path')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    files = ['pma_evidence_review/tests/' + name for name in SUITES]
    with patch.object(runner, 'suite_manifest', return_value=files):
        return runner.run_phase('pma', args.report)


if __name__ == '__main__':
    raise SystemExit(main())
