"""Reproduce public replay against pinned old binder and current projection."""
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

HERE = Path(__file__).resolve().parent
D = HERE.parent
REPO = HERE.parents[3]
sys.path.insert(0, str(D))
spec = importlib.util.spec_from_file_location('replay_tests', D / 'tests/test_gap_evidence_real_replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)
base = replay.FIXTURE['base_commit']
relative = (D / 'gap_evidence.py').relative_to(REPO).as_posix()
code = subprocess.check_output(['git', 'show', f'{base}:{relative}'], cwd=REPO)
old = types.ModuleType('pinned_old_gap_evidence')
sys.modules[old.__name__] = old
exec(compile(code, f'{base}:{relative}', 'exec'), old.__dict__)
rows = replay.replay()
for case, result in zip(replay.FIXTURE['cases'], rows):
    source = replay.FIXTURE['sources'][case['source_key']]
    registry = old.SourceRegistry('real-public-development-replay')
    _, record = old.register_public_source(registry, event_id=source['old_handle'],
        role=source['role'], text=source['raw'], order=source['order'],
        field_path=source['field_path'], record_digest=source['raw_sha256'],
        record_digest_kind='public_prompt_extract')
    rendered = old.render_source_blocks([old.RenderBlock(registry.snapshot(record.source_id))],
                                       cycle_id='offline-public-replay')
    try:
        old.bind_evidence([dict(source=record.handle, quote=case['quote'])], rendered.catalog)
        status = 'accepted'
    except old.SourceScopeError as error:
        status = error.code
    assert status == result['old_format_result']
    result['pinned_baseline_binder_result'] = status
report = dict(scope='offline development replay, public logged evidence references only',
    baseline_commit=base, baseline_binder_sha256=hashlib.sha256(code).hexdigest(),
    current_projection_sha256=hashlib.sha256((D / 'evidence_gap_context.py').read_bytes()).hexdigest(),
    current_binder_sha256=hashlib.sha256((D / 'gap_evidence.py').read_bytes()).hexdigest(),
    references=len(rows), deduplicated_sources=len(replay.FIXTURE['sources']),
    category_counts=dict(Counter(row['expected'] for row in rows)),
    old_result_counts=dict(Counter(row['pinned_baseline_binder_result'] for row in rows)),
    mapped_new_result_counts=dict(Counter(row['projected_mapped_result'] for row in rows)),
    unchanged_parent_result_counts=dict(Counter(row['projected_parent_result'] for row in rows)),
    model_calls=0, real_reruns=0, rows=rows,
    limitations=['Explicit field-path selection remaps citation handles; original quotes are unchanged.',
        'Not an unchanged-response replay: do not claim historical model outputs pass the new API.',
        'No evidence that a model will select child sources, improve decisions, or finish real tasks.',
        'Reference-level checks only, not whole-cycle transaction/ID/tool-call replay.',
        'Historical logs, evaluations, counts, and failures are unchanged. Development data, not holdout.'])
(HERE / 'real_replay_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k not in ('rows', 'limitations')}, indent=2))
