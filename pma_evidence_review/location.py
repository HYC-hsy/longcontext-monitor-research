"""Reuse the existing graded locator over *only* visible rendered slices."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys

from .inputs import D, digest, require


def locate(quotes, packet, repo=None):
    root = Path(repo) if repo else Path(__file__).resolve().parents[1]
    source_root = str(root / D)
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    from gap_evidence import SourceRegistry, register_public_source, VisibleSource, sha256, _key
    from graded_evidence_alignment import align_graded_evidence
    registry = SourceRegistry('offline_review_visible_slices')
    catalog, originals = {}, {}
    for source_index, source in enumerate(packet['sources']):
        for slice_index, piece in enumerate(source['slices']):
            # A new projection ID avoids asserting an unrecoverable full source digest.
            role = source['role'] if source['kind'] == 'public' else 'agent_report'
            _, record = register_public_source(registry,
                event_id='%s:%s' % (source_index, slice_index), role=role,
                text=piece['text'], order=source['event_order'], field_path=source['field_path'],
                record_digest=digest(piece['text']), record_digest_kind='visible_slice_digest')
            catalog[record.handle] = VisibleSource(registry.snapshot(record.source_id),
                ((0, len(piece['text'])),), sha256(_key(packet['cycle_id'],
                    packet['request_sha256'], record.source_id, ((0, len(piece['text'])),))),
                'literal', packet['cycle_id'], packet['request_sha256'])
            originals[record.source_id] = (source, piece)
    aligned = align_graded_evidence([{'quote': q} for q in quotes], catalog)
    result = asdict(aligned)
    for item in result['items']:
        for candidate in item['candidates']:
            source, piece = originals[candidate['source_id']]
            start, end = candidate['start'], candidate['end']
            candidate.update(source_id=source['source_id'], source_kind=source['kind'],
                role=source['role'], start=start + piece['start'], end=end + piece['start'],
                visibility_ref=source['visibility_ref'],
                source_text_sha256=None, original_excerpt=piece['text'][start:end],
                digest_scope='visible_slice_only_not_original_full_source')
    # Only translated references are exposed; upstream metadata uses projection IDs.
    result.pop('bound_refs')
    result['coordinate_scope'] = 'manifest_visible_source_offsets'
    result['semantic_proof'] = False
    return result
