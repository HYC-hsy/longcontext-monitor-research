"""Opt-in citation representation fix; pinned PoS vendor remains byte-identical."""
from __future__ import annotations

import json

from belief.beliefSentinel import BeliefSentinel
from belief.manager import BeliefManager


TOOL_TEXT_KEYS = ('stdout', 'stderr', 'output', 'content', 'text', 'result', 'error')


def _result_fields(value, path):
    """Only explicit tool-return fields; never traverse host or model metadata."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key in TOOL_TEXT_KEYS:
            if key in value:
                yield from _result_fields(value[key], f'{path}.{key}')
    elif isinstance(value, list):
        for index, part in enumerate(value):
            yield from _result_fields(part, f'{path}[{index}]')


def _source_fields(item):
    observation = item.get('observation')
    if not isinstance(observation, str):
        return ()
    try:
        envelope = json.loads(observation)
    except json.JSONDecodeError:
        # An incomplete JSON wrapper is not an unstructured tool receipt.
        return () if observation.lstrip().startswith(('{', '[')) else (('observation', observation),)
    if isinstance(envelope, dict) and isinstance(envelope.get('tool_results'), list):
        fields = []
        for index, receipt in enumerate(envelope['tool_results']):
            if not isinstance(receipt, dict):
                continue
            if 'result' in receipt:
                fields.extend(_result_fields(receipt['result'], f'tool_results[{index}].result'))
            elif 'content' in receipt:
                fields.extend(_result_fields(receipt['content'], f'tool_results[{index}].content'))
        return tuple(fields)
    return ()


def _normal(text: str) -> str:
    # JSON decoding occurred exactly once at the transport wrapper. A literal
    # backslash-n in a tool result is not a newline in that result.
    return ' '.join(text.casefold().split())


class CitationFixedSentinel(BeliefSentinel):
    def _compact_trajectory(self, trajectory):
        compact = super()._compact_trajectory(trajectory)
        for original, shown in zip(trajectory, compact):
            remaining = self.audit_observation_max_chars
            citable = []
            for path, value in _source_fields(original):
                if remaining <= 0:
                    break
                if len(value) > remaining:
                    half = remaining // 2
                    segments = [value[:half], value[-half:]] if half else []
                    truncated = True
                else:
                    segments = [value]
                    truncated = False
                for segment_no, segment in enumerate(segments):
                    if segment:
                        citable.append({'source_path': path, 'segment': segment_no,
                                        'text': segment, 'truncated': truncated})
                        remaining -= len(segment)
            # These exact, separately bounded source fields are included in
            # the audit request. The validator never cites hidden middle text.
            shown['citable_sources'] = citable
        return compact

    @staticmethod
    def _trajectory_text(item: dict) -> tuple[str, ...]:
        if 'citable_sources' in item:
            return tuple(source['text'] for source in item['citable_sources'])
        return tuple(value for _path, value in _source_fields(item))

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
