"""Extend existing strict P1 checks with fake P2-only reader regressions."""
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from pma_evidence_review.tools import run_p1_source_checks as checks


def main():
    # Reuse the existing parser, strict import process and complete P1 inventory.
    original = checks.runner.run_phase
    def with_p2(phase, report):
        files = checks.runner.suite_manifest(phase)+[
            'pma_evidence_review/tests/'+name for name in (
                'test_p2_requirement_view.py','test_p2_requirement_agent.py','test_p2_requirement_reminder.py',
                'test_bank_display.py','test_selection_context.py','test_tag_selection_integration.py')]
        with patch.object(checks.runner,'suite_manifest',return_value=files):
            return original(phase,report)
    with patch('sys.argv',[sys.argv[0],*sys.argv[1:],'--requirement-attributes']), \
            patch.object(checks.runner,'run_phase',side_effect=with_p2):
        return checks.main()


if __name__=='__main__':
    raise SystemExit(main())
