"""Exactly three frozen candidate-only batch calls; no splitter or Task."""
import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from pma_evidence_review import claim_split_semantic as reviewer
from pma_evidence_review import execution_link
from pma_evidence_review.transport import CapturedTransport, load_profile_client

HERE = Path(__file__).resolve().parent
FIX = HERE / 'fixtures'
PARENT = 'a0f35e1ab4586472ebc0768b87e3cc228f36aa14'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
                    encoding='utf-8')


def source_catalog(source_data, selected, label):
    from gap_evidence import SourceRecord, SourceSnapshot, TextBlob, RenderBlock, render_source_blocks, bind_evidence
    from gap_evidence_alignment import _validate_catalog
    sources, cache = source_data['frozen_sources'], {}

    def snapshot(sid):
        if sid not in cache:
            row = sources[sid]
            record = SourceRecord(**row['record'])
            parent = (snapshot(record.parent_wrapper_source_id)
                      if record.parent_wrapper_source_id else None)
            cache[sid] = SourceSnapshot(record, TextBlob(record.text_sha256, row['text']), parent)
        return cache[sid]

    # The local reconstructed catalog includes all fixed visible sources,
    # including unselected opposite-side wrappers needed for call uniqueness.
    # Only the selected literal quotes below are ever projected to the model.
    ids = list(sources)
    parts = render_source_blocks([RenderBlock(snapshot(sid)) for sid in ids], cycle_id=label)
    _validate_catalog(parts.catalog)
    # Re-check exact eligible selected quotes against this newly constructed,
    # explicitly non-historical local visibility catalog; do not add neighbors.
    for item in selected:
        for origin in item['alternative_origins']:
            handle = snapshot(origin['source_id']).record.handle
            bind_evidence([{'source': handle, 'quote': item['submitted_quote']}], parts.catalog)
    inventory = {event_id: {'event_id': event_id, **row}
                 for event_id, row in source_data['frozen_inventory'].items()}
    return execution_link.context_from_inventory(parts.catalog, _validate_catalog, inventory)


def prepared(repo):
    stage = repo / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
    for path in (stage, stage / 'vendor/pma_89e5c0d/src',
                 stage / 'vendor/pma_89e5c0d/external/harbor/src'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    cases = read(FIX / 'frozen_candidate_cases.json')
    offline = read(FIX / 'candidate_model_requests.json')
    assert len(cases) == len(offline) == 3
    prepared_rows = []
    for case, expected in zip(cases, offline):
        assert case['id'] == expected['id']
        source_data = read(FIX / case['host_context_file'])
        context = source_catalog(source_data, case['material']['submitted_evidence'],
                                 'replay-' + case['id'])
        request = {'closed_material': case['material'],
                   'audit_operation_kind': case['operation_kind'],
                   'audit_before_entry': None, 'audit_execution_context': context}
        batch, model_request = reviewer.audit_request(request, case['claims'])
        payload = {k: model_request[k] for k in ('system', 'prompt', 'tools')}
        if payload != expected['model_request']:
            raise ValueError('offline_request_projection_mismatch_' + case['id'])
        if model_request['audit_request_sha256'] != expected['request_sha256']:
            raise ValueError('offline_request_hash_mismatch_' + case['id'])
        prepared_rows.append((case, request, batch, model_request))
    assert cases[0]['material']['submitted_evidence'] == cases[1]['material']['submitted_evidence']
    assert cases[0]['material']['original_operation']['content'] in cases[1]['material']['original_operation']['content']
    return prepared_rows


async def run(args):
    repo, out = Path(args.repo).resolve(), Path(args.out).resolve()
    if out.exists():
        raise ValueError('output_must_not_exist')
    checkout = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    if checkout == PARENT:
        raise ValueError('integration_not_committed')
    rows = prepared(repo)  # all identity/eligibility/plan checks before any call
    out.mkdir(parents=True)
    write(out / 'model_input_plan.json', [
        {'id': case['id'], 'origin': case['origin'], 'model_request':
         {k: model_request[k] for k in ('system','prompt','tools')},
         'audit_request_sha256': model_request['audit_request_sha256'],
         'execution_context_sha256': model_request['execution_context_sha256'],
         'operation_audit_request_id': batch.request_id}
        for case, _, batch, model_request in rows])
    profile = read(Path(args.profile))[args.profile_key]
    keys = ('provider','api_mode','model','thinking_type','temperature',
            'reasoning_effort','max_tokens','read_timeout')
    safe_profile = {key: profile.get(key, 'default/unknown') for key in keys}
    if (safe_profile['provider'], safe_profile['api_mode'], safe_profile['model'],
            safe_profile['thinking_type']) != ('anthropic','messages','claude-opus-4-8','adaptive'):
        raise ValueError('model_identity_changed')
    write(out / 'run_identity.json', {'execution_code_sha': checkout,
        'production_parent_sha': PARENT, 'review_strategy': reviewer.STRATEGY,
        'profile_key': args.profile_key, 'safe_profile_fields': safe_profile,
        'frozen_case_sha256': sha256((FIX / 'frozen_candidate_cases.json').read_bytes()).hexdigest(),
        'requests': [{'id': case['id'],
            'audit_request_sha256': model_request['audit_request_sha256'],
            'system_sha256': sha256(model_request['system'].encode()).hexdigest(),
            'execution_context_sha256': model_request['execution_context_sha256']}
            for case, _, _, model_request in rows]})
    client = load_profile_client(repo, args.profile, args.profile_key, out / 'private_client',
                                 authorized=True)
    transport, results = CapturedTransport(client, out), []
    for case, request, _, _ in rows:
        try:
            value = await reviewer.review_stage(request, transport,
                {'engineering_status': 'split_ready', 'claims': case['claims']})
            results.append({'id': case['id'], 'result': value,
                            'client_calls_so_far': transport.calls})
            write(out / 'results.json', results)
            if value['engineering_status'] != 'ok':
                break
        except Exception as error:
            results.append({'id': case['id'], 'engineering_status': 'exception',
                            'error_type': type(error).__name__,
                            'client_calls_so_far': transport.calls})
            write(out / 'results.json', results)
            break
    write(out / 'stop_state.json', {'completed_cases': len(results),
        'client_calls': transport.calls,
        'unrun_ids': [row[0]['id'] for row in rows[len(results):]],
        'stopped_on_engineering_error': bool(results and
            results[-1].get('engineering_status',
                results[-1].get('result', {}).get('engineering_status')) != 'ok')})
    return 0 if len(results) == 3 and not read(out / 'stop_state.json')['stopped_on_engineering_error'] else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--repo', required=True)
    p.add_argument('--profile', required=True)
    p.add_argument('--profile-key', default='claude_monitor_opus48')
    p.add_argument('--out', required=True)
    sys.exit(asyncio.run(run(p.parse_args())))
