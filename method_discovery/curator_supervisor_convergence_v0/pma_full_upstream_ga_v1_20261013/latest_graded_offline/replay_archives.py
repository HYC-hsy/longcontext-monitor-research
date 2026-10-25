"""Offline archive replay; no models, Tasks, evaluations, or archive mutation."""
import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path
from collections import Counter
from dataclasses import asdict
from gap_evidence import RenderBlock, SourceRecord, SourceRegistry, VisibleSource, render_source_blocks, sha256
from graded_evidence_alignment import align_graded_evidence, FUZZY_WORK_LIMIT
from gap_evidence_alignment import align_evidence
from latest_evidence_gap_store import LatestEvidenceGapMemory
from test_gap_evidence_alignment import catalog_for
D = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--sqlite-memory', type=Path, required=True)
parser.add_argument('--sqlite-events', type=Path, required=True)
parser.add_argument('--html-memory', type=Path, required=True)
parser.add_argument('--html-events', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
out = {'scope': 'offline deterministic archive replay, not effectiveness validation',
    'model_calls': 0,
    'real_tasks': 0,
    'fuzzy_work_limit': FUZZY_WORK_LIMIT,
    'archives': {},
    'results': []}

def load(p):
    return json.loads(Path(p).read_text())['value']

def registry_for(data):
    g = data['gap_evidence']
    namespace = next(iter(g['sources'].values()))['namespace']
    reg = SourceRegistry(namespace)

    def retain(sid):
        if sid in reg.sources:
            return reg.snapshot(sid)
        r = g['sources'][sid]
        parent = retain(r['parent_wrapper_source_id']) if r['parent_wrapper_source_id'] else None
        if sha256(g['blobs'][r['text_sha256']]) != r['text_sha256'] or (r['parent_wrapper_source_id'] and parent is None):
            return None
        reg._register(SourceRecord(**r), g['blobs'][r['text_sha256']], parent)
        return reg.snapshot(sid)
    for sid in g['sources']:
        retain(sid)
    return reg
for name, mp, ep in [('sqlite',
    args.sqlite_memory,
    args.sqlite_events),
    ('html',
    args.html_memory,
    args.html_events)]:
    data = load(mp)
    g = data['gap_evidence']
    reg = registry_for(data)
    catalogs = {}
    coverage = []
    for cid, m in g['manifests'].items():
        catalog = {}
        missing = []
        for sid, spans, vref in zip(m['ordered_source_refs'],
            m['visible_spans'],
            m['visibility_refs']):
            if sid not in reg.sources:
                missing.append(sid)
                continue
            snap = reg.snapshot(sid)
            v = VisibleSource(snap, spans, vref, 'literal', cid, m['request_sha256'])
            catalog[snap.record.handle] = v
        catalogs[cid] = catalog
        coverage.append({'cycle_id': cid,
            'manifest_sources': len(m['ordered_source_refs']),
            'reconstructed_sources': len(catalog),
            'missing_sources': missing})
    oldcounts = Counter()
    newcounts = Counter()
    timings = []
    for rid, row in data['gap_alignment']['alignments'].items():
        old = json.loads(row['alignment_json'])
        ev = [dict(quote=i['quote'],
            **{'source': i['source_hint']} if i['source_hint'] is not None else {}) for i in old['items']]
        catalog = catalogs[row['cycle_id']]
        t = time.perf_counter()
        new = align_graded_evidence(ev, catalog)
        timings.append(time.perf_counter() - t)
        literal = align_evidence(ev, catalog)
        same_literal = json.loads(json.dumps([asdict(i) for i in literal.items])) == old['items']
        for a, b in zip(old['items'], new.items):
            oldcounts[a['status']] += 1
            newcounts[b.status] += 1
        out['results'].append({'archive': name,
            'revision_id': rid,
            'cycle_id': row['cycle_id'],
            'literal_replay_identical': same_literal,
            'old_status': old['status'],
            'old_disposition': row['disposition'],
            'new': asdict(new)})
    out['archives'][name] = {'input_memory_sha256': hashlib.sha256(Path(mp).read_bytes()).hexdigest(),
        'input_events_sha256': hashlib.sha256(Path(ep).read_bytes()).hexdigest(),
        'catalog_coverage': coverage,
        'old_quote_counts': dict(oldcounts),
        'new_quote_counts': dict(newcounts),
        'alignment_calls': len(timings),
        'single_pass_seconds': sum(timings),
        'max_call_seconds': max(timings),
        'all_literal_replays_identical': all((r['literal_replay_identical'] for r in out['results'] if r['archive'] == name))}
fixture = json.loads((D / 'tests/graded_c8_alignment_fixture.json').read_text())
event = next((json.loads(l)['value']['event'] for l in Path(args.sqlite_events).read_text().splitlines() if json.loads(l)['value']['event']['sequence'] == 15))
stdout = json.loads(json.loads(event['observation'])['tool_results'][0]['content'])['stdout']
assert stdout == fixture['source'] and sha256(stdout) == fixture['source_sha256']
out['c8_authoritative'] = {'event_sequence': 15,
    'event_id': event['event_id'],
    'source_sha256': sha256(stdout),
    'fixture_equal': True,
    'quote_count': len(fixture['quotes']),
    'grades': [align_graded_evidence([{'quote': q}],
    catalog_for(stdout)).status for q in fixture['quotes']]}
negative = align_graded_evidence([{'quote': 'all tests passed successfully today'}],
    catalog_for('all tests NOT passed successfully today'))
budget = align_graded_evidence([{'quote': ' '.join(['needle'] * 100)}],
    catalog_for(' '.join(['haystack'] * 1000)))
out['synthetic_diagnostics'] = {'negation_candidate': asdict(negative),
    'budget_exceeded': asdict(budget),
    'interpretation': 'fuzzy_candidate is not semantic support; budget refusal is not a Task failure'}
sql = load(args.sqlite_memory)
row = sql['gap_alignment']['alignments']['rev_29878d2799a740b6a57345fde74768a2']
value = json.loads(row['alignment_json'])
quote = value['items'][0]['quote']
parent_id = next((r['parent_revision_id'] for r in value['items'][0]['candidates'] if r['parent_revision_id'] and sql['gap_alignment']['alignments'][r['parent_revision_id']]['disposition'] == 'unbound'))
content = sql['gap_evidence']['blobs'][sql['gap_evidence']['revisions'][parent_id]['content_sha256']]
bank = LatestEvidenceGapMemory()
parts = render_source_blocks([], cycle_id='new-parent')
draft = bank.fork_write_draft()
draft.retain_manifest(parts)
key, _, _ = draft.apply_aligned_write('procedural',
    content,
    align_graded_evidence([],
    parts.catalog),
    cycle_id='new-parent',
    op_index=0)
bank.publish(bank.prepare_publication(draft))
reg = SourceRegistry('new-c6')
r = bank.memory_source(reg, key)
blocks = [RenderBlock(reg.snapshot(r.source_id))]
oldreg = registry_for(sql)
for ref in value['bound_refs']:
    if not ref['parent_revision_id'] and ref['source_id'] in oldreg.sources:
        snap = oldreg.snapshot(ref['source_id'])
        if all((b.snapshot.record.source_id != snap.record.source_id for b in blocks)):
            blocks.append(RenderBlock(snap))
parts = render_source_blocks(blocks, cycle_id='new-c6')
alignment = align_graded_evidence([{'quote': quote}], parts.catalog)
draft = bank.fork_write_draft()
draft.retain_manifest(parts)
key, rid, disposition = draft.apply_aligned_write('procedural',
    'C6 replay claim',
    alignment,
    cycle_id='new-c6',
    op_index=0)
bank.publish(bank.prepare_publication(draft))
bank.validate_bank()
record = bank.binding(key)
out['c6_new_store'] = {'scope': 'Actual first C6 quote and retained source texts; fresh bank, reconstructed unbound parent, not full C6 operation replay or historical migration',
    'disposition': disposition,
    'status': record.status,
    'provenance_summary': record.provenance_summary,
    'candidate_provenance': json.loads(record.candidate_provenance_json),
    'roundtrip_equal': LatestEvidenceGapMemory.from_dict(bank.to_dict()).to_dict() == bank.to_dict()}
assert disposition == 'bound' and record.provenance_summary == 'mixed'
bench = []
for name, source, q in [('exact',
    stdout,
    fixture['quotes'][0][:40]),
    ('normalized',
    stdout,
    fixture['quotes'][0]),
    ('fuzzy_negation',
    'all tests NOT passed successfully today',
    'all tests passed successfully today'),
    ('budget_not_searched',
    ' '.join(['haystack'] * 1000),
    ' '.join(['needle'] * 100))]:
    catalog = catalog_for(source)
    samples = []
    for _ in range(10):
        t = time.perf_counter()
        result = align_graded_evidence([{'quote': q}], catalog)
        samples.append(time.perf_counter() - t)
    bench.append({'case': name,
        'source_chars': len(source),
        'quote_chars': len(q),
        'repetitions': 10,
        'warmup': 0,
        'status': result.status,
        'reason': result.items[0].reason,
        'fuzzy_search': result.items[0].metadata.get('fuzzy_search'),
        'min_seconds': min(samples),
        'median_seconds': statistics.median(samples),
        'max_seconds': max(samples)})
out['benchmark'] = bench
c8_manifest = sql['gap_evidence']['manifests']['cycle_9a70b9d99d774d9397131531d44e3c85']
spans = [sp for sid,
    sp in zip(c8_manifest['ordered_source_refs'],
    c8_manifest['visible_spans']) if json.loads(sid)[-2:] == [event['event_id'],
    'observation/tool_results/0/content/stdout']]
assert spans == [[[0, len(stdout)]]]
out['c8_authoritative']['original_manifest_visible_spans'] = spans[0]
out['c8_authoritative']['scope'] = 'Actual original C8 stdout visible projection, not full multi-source catalog uniqueness certification'
out['c5_omission_quotes'] = [{'revision_id': r['revision_id'],
    'status': i['status'],
    'reason': i['reason']} for r in out['results'] for i in r['new']['items'] if '[hidden gap]' in i['quote']]
assert len(out['c5_omission_quotes']) == 3 and all((r['status'] == 'unbound' for r in out['c5_omission_quotes']))
out['limitations'] = ['Public-projection source bytes differ from retained original hashes, consistent with redaction. This is not evidence of archive or private-source corruption.',
    'Four SQLite public-projection blobs differ from retained original hashes; affected sources and dependent child snapshots were excluded, without recomputing original hashes.',
    'Offline archive replay does not measure model behavior or online effectiveness.',
    'Replay catalogs contain only retained original source snapshots reconstructed with original per-cycle manifest spans. Missing unmatched sources prevent whole-catalog uniqueness/completeness certification. This is not full-catalog replay or replay of model calls.',
    'Synthetic negatives can have fuzzy lexical candidates; candidates must not be read as semantic proof.',
    'Timing is local single-pass wall time, not a statistically stable performance estimate.']
g = sql['gap_evidence']
bad = [k for k, v in g['blobs'].items() if sha256(v) != k]
out['public_projection_hash_differences'] = [{'retained_original_sha256': k,
    'contains_redaction_marker': '[REDACTED]' in g['blobs'][k],
    'source_records': [{'source_id': sid,
    'event_id': r['event_id'],
    'field_path': r['field_path'],
    'source_kind': r['source_kind']} for sid,
    r in g['sources'].items() if r['text_sha256'] == k]} for k in bad]
args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k,
    v in out.items() if k not in ['results',
    'synthetic_diagnostics',
    'c6_new_store']},
    indent=2))
