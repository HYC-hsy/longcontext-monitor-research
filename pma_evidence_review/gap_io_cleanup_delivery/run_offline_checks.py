"""Combined candidate checks; scripted clients only, no experiments."""
import sys
import unittest
from pma_evidence_review.tests.runtime_boundary_support import IMPORT_DOUBLES
from pma_evidence_review.runtime_boundary_repair.run_offline_checks import MODULES, OMITTED, leaves


if __name__ == '__main__':
    print('Optional dependency doubles:', IMPORT_DOUBLES, flush=True)
    print('Excluded existing frozen-dataset check:', OMITTED, flush=True)
    modules = MODULES + ('test_gap_audit_contract', 'test_operation_audit_integration',
                         'test_selection_context')
    suite = unittest.TestSuite(test for name in modules
        for test in leaves(unittest.defaultTestLoader.loadTestsFromName(
            'pma_evidence_review.tests.' + name)) if test._testMethodName != OMITTED)
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
