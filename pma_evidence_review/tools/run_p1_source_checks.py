"""Strict P1-only offline checks; no P2, task or real provider execution."""
import argparse
import os
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ['PMA_TEST_STRICT_IMPORTS']='1'
os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
from pma_evidence_review.tests import run_gate_regressions as runner


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',required=True,type=Path)
    parser.add_argument('--source-links',action='store_true',help='also verify the independent linked-source P1 candidate')
    parser.add_argument('--dms',action='store_true',help='verify independent DMS-inspired P1')
    args=parser.parse_args()
    if args.report.exists():
        raise FileExistsError('use a new report path')
    args.report.parent.mkdir(parents=True,exist_ok=True)
    files=['pma_evidence_review/tests/'+name for name in (
        'test_p1_source_archive.py','test_p1_source_agent.py',
        'test_p1_source_client.py','test_p1_source_cases.py','test_p1_source_isolation.py')]
    if args.source_links or args.dms:
        files += ['pma_evidence_review/tests/test_p1_source_links.py',
                  'pma_evidence_review/tests/test_p1_linked_agent.py',
                  'pma_evidence_review/tests/test_p1_linked_runner.py']
    if args.dms:
        files += ['pma_evidence_review/tests/test_p1_dms.py',
                  'pma_evidence_review/tests/test_dms_receipt_view.py']
    with patch.object(runner,'suite_manifest',return_value=files):
        return runner.run_phase('pma',args.report)


if __name__=='__main__':
    raise SystemExit(main())
