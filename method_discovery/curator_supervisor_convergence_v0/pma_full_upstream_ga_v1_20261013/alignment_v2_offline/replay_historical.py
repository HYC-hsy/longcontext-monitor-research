"""Offline unchanged-quote/hint replay over same-prompt public source projection."""
from collections import Counter
from dataclasses import asdict
import gzip
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
D = HERE.parent
REPO = HERE.parents[3]
sys.path.insert(0, str(D))
from evidence_gap_context import _project_tool_text
from gap_evidence import RenderBlock, SourceRegistry, excerpt, register_public_source, render_source_blocks, sha256
from gap_evidence_alignment import align_evidence

OLD = D / 'evidence_interface_repair_v1_offline'
FIXTURE = json.loads((OLD / 'real_public_fixture.json').read_text(encoding='utf-8'))
spec = importlib.util.spec_from_file_location('historical_public_extractor', OLD / 'extract_real_replay.py')
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)
PUBLIC_ROLES = {'task_instruction', 'tool_observation', 'agent_report', 'tool_command'}


def render_sources(sources, cycle_id):
    registry, blocks = SourceRegistry('alignment-v2-public-prompt-replay'), []
    for source in sources:
        parents = {}
        identity = dict(source_id=source['old_handle'], order=source['order'],
                        record_digest=source['raw_sha256'], record_digest_kind='public_prompt_extract')

        def add(identity, role, text, path, **meta):
            _, record = register_public_source(registry, event_id=identity['source_id'],
                role=role, text=text, order=identity['order'], field_path=path,
                record_digest=identity['record_digest'], record_digest_kind=identity['record_digest_kind'],
                parent_wrapper_source_id=parents.get(meta.get('parent_field_path')),
                tool_call_id=meta.get('tool_call_id'))
            parents[path] = record.source_id
            blocks.append(RenderBlock(registry.snapshot(record.source_id), meta.get('render_spans')))

        _project_tool_text(add, identity, source['role'], source['raw'], source['field_path'])
    return render_source_blocks(blocks, cycle_id=cycle_id)


def prompt_sources(case):
    archive = REPO / case['prompt_archive']
    blob = archive.read_bytes()
    assert sha256_bytes(blob) == FIXTURE['archives_sha256'][case['prompt_archive']]
    record = json.loads(gzip.decompress(blob).splitlines()[case['prompt_line'] - 1])
    assert record['source_line_sha256'] == case['prompt_source_line_sha256']
    sources, omitted = [], Counter()
    for match in extractor.HEADER.finditer(record['value']['prompt']):
        raw, role = match[5].rstrip('\n'), match[2]
        if role not in PUBLIC_ROLES or not raw:
            omitted[role if raw else 'empty_text'] += 1
            continue
        sources.append(dict(old_handle=match[1], role=role, order=int(match[3]),
                            field_path=match[4], raw=raw, raw_sha256=sha256(raw)))
    original = FIXTURE['sources'][case['source_key']]
    assert original in sources
    return sources, dict(omitted)


def sha256_bytes(value):
    import hashlib
    return hashlib.sha256(value).hexdigest()


def replay():
    rows, cache = [], {}
    for case in FIXTURE['cases']:
        key = (case['prompt_archive'], case['prompt_line'])
        if key not in cache:
            sources, omitted = prompt_sources(case)
            rendered = render_sources(sources, f'{key[0]}:{key[1]}')
            cache[key] = sources, omitted, rendered
        sources, omitted, rendered = cache[key]
        old_hint = FIXTURE['sources'][case['source_key']]['old_handle']
        evidence = [dict(source=old_hint, quote=case['quote'])]
        result = align_evidence(evidence, rendered.catalog)
        no_hint = align_evidence([dict(quote=case['quote'])], rendered.catalog)
        assert result.bound_refs == no_hint.bound_refs
        resolver = {v.visibility_ref: v for v in rendered.catalog.values()}
        candidates = []
        for ref in result.bound_refs:
            visible = resolver[ref.visibility_ref]
            assert excerpt(ref, resolver) == case['quote']
            candidates.append(dict(**asdict(ref),
                generated_handle=visible.snapshot.record.handle,
                historical_event_handle=visible.snapshot.record.event_id,
                field_path=visible.snapshot.record.field_path))
        rows.append(dict(case_id=case['case_id'], quote=case['quote'],
            quote_sha256=sha256(case['quote']), original_hint=old_hint,
            original_hint_present_in_new_catalog=old_hint in rendered.catalog,
            historical_category=case['expected'], status=result.status,
            reason=result.reason, candidates=candidates,
            public_source_count=len(sources), projected_catalog_count=len(rendered.catalog),
            omitted_prompt_source_counts=omitted,
            prompt_archive=case['prompt_archive'], prompt_line=case['prompt_line'],
            prompt_source_line_sha256=case['prompt_source_line_sha256'],
            transport_archive=case['transport_archive'], transport_line=case['transport_line']))
    return rows


def main():
    rows = replay()
    report = dict(scope='Offline development binding replay; unchanged historical quotes and source hints',
        historical_fixture_sha256=sha256_bytes((OLD / 'real_public_fixture.json').read_bytes()),
        implementation_sha256={name: sha256_bytes((D / name).read_bytes()) for name in
            ('gap_evidence_alignment.py', 'gap_evidence.py', 'evidence_gap_context.py')},
        references=len(rows), result_counts=dict(Counter(r['status'] for r in rows)),
        model_calls=0, real_task_runs=0, hidden_evaluator_reads=0,
        limitations=[
            'Only same-prompt public source headers are rebuilt; no adjacent-cycle sources or hidden data.',
            'Memory-derived prompt entries are omitted: authentic revision identities cannot be recovered from these snippets.',
            'Historical visible prompt excerpts are not original event envelopes; digest kind is public_prompt_extract.',
            'Projection creates a new decoded catalog, not the identical historical request or source IDs.',
            '32 selected historically failed references, not independent tasks or whole transaction replay.',
            'Binding improvement does not establish changed model behavior, semantic support, or task completion.',
            'Historical archives, quotes, hints, evaluation, and previous replay artifacts are untouched.'], rows=rows)
    (HERE / 'replay_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('references', 'result_counts', 'model_calls', 'real_task_runs')}, indent=2))


if __name__ == '__main__':
    main()
