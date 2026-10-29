"""Focused offline gate suite; no lifecycle or model execution."""
import unittest
from pma_evidence_review.tests import test_live_gate

loader = unittest.defaultTestLoader
suite = unittest.TestSuite()
for name in (
    'pma_evidence_review.tests.test_simple_split_pipeline',
    'pma_evidence_review.tests.test_simple_split_bindings',
    'pma_evidence_review.tests.test_claim_split_live',
):
    suite.addTests(loader.loadTestsFromName(name))
for test in loader.loadTestsFromTestCase(test_live_gate.LiveGateTests):
    # This lifecycle binding check needs modules outside the sparse working tree.
    if test._testMethodName != 'test_harbor_binding_and_source_validation':
        suite.addTest(test)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
