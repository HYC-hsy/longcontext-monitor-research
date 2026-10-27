"""Reproducible offline runner for citation + affected pinned PMA tests.
Python <3.12 gets test-import-only TypedDict compatibility; vendor bytes unchanged.
"""
import importlib.metadata
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.inputs import D


def main():
    root=Path(__file__).resolve().parents[2]
    os.chdir(root)
    stage=root/D
    for path in (stage,stage/'vendor/pma_89e5c0d/src',stage/'vendor/pma_89e5c0d/external/harbor/src'):
        sys.path.insert(0,str(path))
    os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
    original=importlib.metadata.version
    def version(name):
        try:return original(name)
        except importlib.metadata.PackageNotFoundError:
            if name=='harbor':return '0.0.0-source-checkout-test-only'
            raise
    import typing_extensions
    guard=unittest.TestCase();install_guard(guard)
    try:
        # Only compatibility at imports; actual host/worker/agent code executes.
        with patch('importlib.metadata.version',side_effect=version),patch('typing.TypedDict',typing_extensions.TypedDict):
            suite=unittest.TestLoader().discover(str(root/'pma_evidence_review/tests'),pattern='test_*.py')
            for name in ('test_gap_latest_revision_store.py','test_gap_latest_revision_agent.py',
                         'test_gap_evidence_agent.py','test_gap_evidence_store.py',
                         'test_gap_evidence_host.py','test_gap_evidence_aligned_host.py',
                         'test_gap_evidence_alignment_integration.py','test_gap_host_integration.py',
                         'test_evaluation_bootstrap.py'):
                if name=='test_evaluation_bootstrap.py' and sys.version_info<(3,12):
                    skipped=unittest.skip('Pinned native Harbor verifier requires Python 3.12 syntax; not executed')(lambda:None)
                    suite.addTest(unittest.FunctionTestCase(skipped))
                else:
                    suite.addTests(unittest.TestLoader().discover(str(stage/'tests'),pattern=name))
            result=unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    finally:
        guard.doCleanups()


if __name__=='__main__':raise SystemExit(main())
