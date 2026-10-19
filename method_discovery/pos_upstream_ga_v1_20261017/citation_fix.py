"""Opt-in citation representation fix; pinned PoS vendor remains byte-identical."""
from __future__ import annotations

import json

from belief.beliefSentinel import BeliefSentinel
from belief.manager import BeliefManager


def _fields(value, *, depth=0):
    """Return individual decoded source fields, never a concatenated wrapper."""
    if isinstance(value, dict):
        if value.get('role') in {'assistant', 'system', 'user'}:
            return
        for item in value.values():
            yield from _fields(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            yield from _fields(item, depth=depth + 1)
    elif isinstance(value, str):
        if depth < 8 and value.lstrip().startswith(('{', '[')):
            try:
                nested = json.loads(value)
            except json.JSONDecodeError:
                pass
            else:
                yield from _fields(nested, depth=depth + 1)
                return
        yield value


def _normal(text: str) -> str:
    # JSON transport may leave literal escapes in a source field; compare
    # their decoded spelling without changing case/whitespace policy.
    text = text.replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\t', '\t')
    text = text.replace('\\"', '"')
    return ' '.join(text.casefold().split())


class CitationFixedSentinel(BeliefSentinel):
    @staticmethod
    def _trajectory_text(item: dict) -> tuple[str, ...]:
        # The original JSON serialization escaped newlines and joined action
        # and observation, allowing a false quote across their boundary.
        return tuple(_fields(item.get('action'))) + tuple(_fields(item.get('observation')))

    @staticmethod
    def _valid_issue(issue, valid_targets, evidence_by_step) -> bool:
        if not issue.targets or not set(issue.targets) <= valid_targets:
            return False
        fields = evidence_by_step.get(issue.evidence_step)
        if fields is None:
            return False
        quote = _normal(issue.evidence_quote)
        return bool(quote and any(quote in _normal(field) for field in fields))


class CitationFixedBeliefManager(BeliefManager):
    """Reuse the released manager, replacing only its newly created Sentinel."""

    def __init__(self, config, call_model, logger, call_sentinel=None,
                 call_progress=None):
        super().__init__(config, call_model, logger, call_sentinel=call_sentinel,
                         call_progress=call_progress)
        if self.sentinel is not None:
            sentinel_config = dict(self.sentinel.config)
            self.sentinel = CitationFixedSentinel(
                sentinel_config, call_sentinel, logger,
                call_progress_model=call_progress)
