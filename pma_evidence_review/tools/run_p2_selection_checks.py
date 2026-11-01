"""Strict offline P2 wiring regressions using the existing guarded PMA runner."""
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

SUITES = (
    'test_selection_judgment_prompt.py', 'test_tag_selection_integration.py',
    'test_selection_context.py', 'test_selection_deployment.py',
    'test_verbatim_selection_integration.py', 'test_maintenance_no_review.py',
    'test_maintenance_policy.py', 'test_maintenance_episode.py',
)


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
