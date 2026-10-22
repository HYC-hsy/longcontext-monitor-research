"""Frozen stateful transport policies; optional archives are not the memory store."""

import sys


POLICY_CHOICES = {
    'native_context_policy': ('required', 'off'),
    'research_capture_policy': ('required', 'best_effort'),
}


def policies(record):
    result = {name: record.get(name, 'required') for name in POLICY_CHOICES}
    for name, choices in POLICY_CHOICES.items():
        if result[name] not in choices:
            raise ValueError('invalid stateful ' + name)
    return result


def require_same_policies(frozen, other):
    expected = policies(frozen)
    if policies(other) != expected:
        raise ValueError('stateful runtime policies differ from frozen configuration')
    return expected


class ResearchArchive:
    """Guard only auxiliary research writes, never SQLite/CAS or spool receipts."""

    def __init__(self, policy='required'):
        self.policy = policies({'research_capture_policy': policy})['research_capture_policy']
        self.evidence_gaps = 0

    def write(self, writer, path, row):
        try:
            writer(path, row)
        except Exception as error:
            if self.policy == 'required':
                raise
            self.evidence_gaps += 1
            try:
                print('stateful research capture evidence_gap: ' +
                      type(error).__name__, file=sys.stderr)
            except Exception:
                pass
