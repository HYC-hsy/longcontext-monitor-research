"""Targeted engineering checks; no model, Task, evaluator or network run."""
import sys
import unittest
from pma_evidence_review.tests.runtime_boundary_support import IMPORT_DOUBLES

MODULES = ('test_runtime_boundary', 'test_ga_spool_import_boundary', 'test_execution_link_integration',
           'test_claim_split', 'test_claim_split_simple', 'test_claim_split_semantic')
OMITTED = 'test_frozen_small_comparison_materials_and_delete_na'


def leaves(suite):
    for value in suite:
        if isinstance(value, unittest.TestSuite):
            yield from leaves(value)
        else:
            yield value


if __name__ == '__main__':
    print('Optional dependency doubles:', IMPORT_DOUBLES, flush=True)
    print('Excluded frozen-dataset comparison-plan check:', OMITTED,
          '(dataset is outside this scoped source snapshot)', flush=True)
    suite = unittest.TestSuite(test for name in MODULES
        for test in leaves(unittest.defaultTestLoader.loadTestsFromName(
            'pma_evidence_review.tests.' + name)) if test._testMethodName != OMITTED)
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
