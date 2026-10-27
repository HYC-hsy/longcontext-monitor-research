"""Benchmark adapter: independent derived identities, frozen citation-only requests."""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

from .. import inputs as old, citation_inputs as ci, citation_review as cr
from ..transport import CapturedTransport, FakeClient, ResponseProtocolError

SOURCE_COMMIT = '72152913f545ca36a75b68e8796e24a6e24f9f81'
CODE_COMMIT = 'a4aeb1fb940bda72df8558c1dc6b935019ae36d9'
LABELS = ('supported', 'insufficient', 'contradicted')
ROOT = old.D / 'source_window_two_real_20261025'


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def checked_file(repo, relative):
    """Only fixed public repository bytes; fail if local files differ."""
    # Git object names and persisted provenance are POSIX, even on Windows.
    object_path = relative.as_posix()
    frozen = subprocess.check_output(['git', 'show', SOURCE_COMMIT+':'+object_path], cwd=repo, env={**os.environ, 'GIT_NO_LAZY_FETCH':'1'})
    current = (Path(repo)/relative).read_bytes()
    old.require(current == frozen, 'public_commit_file_mismatch')
    return {'commit': SOURCE_COMMIT, 'path': object_path,
            'sha256': hashlib.sha256(current).hexdigest(), 'bytes': len(current)}


def inventory(repo):
    cycles, packets, files = [], {}, []
    files.append(checked_file(repo, ROOT/'INDEX.json'))
    for sample, (slot, _, _) in old.SAMPLES.items():
        relative = ROOT/slot
        files.append(checked_file(repo, relative/'INDEX.json'))
        index = json.loads((Path(repo)/relative/'INDEX.json').read_text(encoding='utf-8'))['files']
        loaded = {}
        for name, lines in [('memory_payload.jsonl.gz', True), ('trajectory_memory.json.gz', False),
                            ('gap_cycle.jsonl.gz', True), ('memory.json.gz', False)]:
            files.append(checked_file(repo, relative/name))
            loaded[name] = old.load_indexed(Path(repo)/relative/name, index, lines)
        bank = loaded['memory.json.gz']; store = bank['gap_evidence']
        for payload in loaded['memory_payload.jsonl.gz']:
            if payload.get('phase') != 'maintenance':
                continue
            step = payload['cycle_step']
            trace = old.only(loaded['trajectory_memory.json.gz']['steps'],
                             lambda r: r.get('step_id') == step, 'step_identity')
            entry = {'sample': sample, 'step': step, 'sequence': payload['call_sequence'],
                     'operation_count': len(trace['operations'])}
            cycles.append(entry)
            matches = [k for k, v in store['manifests'].items()
                       if v['request_sha256'] == old.digest(payload['prompt'])]
            if len(matches) != 1:
                entry['excluded'] = 'public_prompt_no_exact_manifest_match'
                cycle = old.only(loaded['gap_cycle.jsonl.gz'], lambda r:r.get('step')==step,'cycle_step')
                revision_ids = [r.get('revision_id') for r in cycle['evidence_report']['operations']]
                alignments = bank['gap_alignment']['alignments']
                ids = sorted({alignments[r]['cycle_id'] for r in revision_ids if r in alignments})
                entry['operations'] = [{'op_index':i,'action':op.get('action'),
                    'revision_id':cycle['evidence_report']['operations'][i].get('revision_id'),
                    'preparation':'cycle_input_unverifiable',
                    'issues':['public_prompt_no_exact_manifest_match']}
                    for i,op in enumerate(trace['operations'])]
                entry['identity_diagnostic'] = {
                    'public_prompt_sha256':old.digest(payload['prompt']),
                    'historical_cycle_candidates':ids,
                    'original_manifest_sha256':{k:store['manifests'][k]['request_sha256'] for k in ids},
                    'redaction_marker_count':payload['prompt'].count('[REDACTED]'),
                    'first_redaction_character':payload['prompt'].find('[REDACTED]'),
                    'comparison':'sha256(maintenance.prompt) vs manifest.request_sha256; no normalization',
                    'cause':'public redaction marker present' if '[REDACTED]' in payload['prompt']
                            else 'unresolved mismatch; not assumed adapter failure'}
                continue
            entry['cycle_id'] = matches[0]
            try:
                parent = old.build(repo, sample, step=step, cycle_id=matches[0])
                records = {}
                for source in parent['sources']:
                    record = store['sources'].get(source['source_id'])
                    if record is None:
                        continue
                    text = store['blobs'][record['text_sha256']]
                    old.require(old.digest(text) == record['text_sha256'], 'source_blob_hash')
                    old.require(all(text[p['start']:p['end']] == p['text'] for p in source['slices']),
                                'source_visible_mismatch')
                    records[source['source_id']] = record
                packet = ci.build_from_parent(parent, bank['gap_alignment']['alignments'],
                                              source_records=records)
                packets[f'{sample}-{step}'] = packet
                entry['operations'] = [{'op_index': r['operation']['op_index'],
                    'revision_id': r['operation']['revision_id'], 'action': r['operation']['action'],
                    'preparation': r['preparation']['status'], 'issues': r['preparation']['issues']}
                    for r in packet['operations']]
            except (ValueError, KeyError) as e:
                entry['excluded'] = str(e)
    return {'files': files, 'cycles': cycles}, packets


def quoted_source(packet, selector):
    """Exact literal slice only, no execution, fuzzy matching or neighbor expansion."""
    parent = packet['host_provenance']
    source = old.only(parent['sources'], lambda s: s['field_path'] == selector['field'] and
                      (not selector.get('event') or json.loads(s['source_id'])[2] == selector['event']),
                      'benchmark_source_ambiguous')
    matches = []
    for piece in source['slices']:
        text = piece['text']; quote = selector.get('quote', text)
        start = 0
        while quote and (pos := text.find(quote, start)) >= 0:
            matches.append((piece['start']+pos, quote)); start = pos+1
    old.require(len(matches) == 1, 'benchmark_quote_not_unique')
    start, quote = matches[0]
    record = packet['source_records'].get(source['source_id'])
    if record is None:
        # Benchmark-selected literal span: no invented full-source digest or historical binding.
        ref = {'source_id':source['source_id'], 'source_kind':source['kind'],
               'role':source['role'], 'order':source['event_order'], 'start':start,
               'end':start+len(quote), 'snippet_sha256':old.digest(quote),
               'visibility_ref':source['visibility_ref'], 'source_text_sha256':None}
        bound = {'reference':ref, 'original_excerpt':quote, 'field_path':source['field_path'],
                 'handle':source['handle'], 'source_text_hash_check':'unavailable_not_asserted',
                 'binding_origin':'benchmark_visible_literal_selection',
                 'coordinate_unit':'python_unicode_code_points'}
        return {'submitted_quote':quote,'candidates':[bound]}
    ref = {k: record.get(k) for k in ('source_id','source_kind','role','order',
                                    'parent_revision_id','parent_wrapper_source_id')}
    ref.update(start=start, end=start+len(quote), source_text_sha256=record['text_sha256'],
               snippet_sha256=old.digest(quote), visibility_ref=source['visibility_ref'])
    bound = ci.candidate(ref, parent, packet['source_records'])
    return {'submitted_quote': quote, 'candidates': [bound]}


def build_case(spec, packet):
    """Never mutate or weaken a historical packet to make a derived operation pass."""
    ci.validate(packet)
    origin = packet['operations'][spec['op_index']]
    old.require(origin['preparation']['status'] == 'ready', 'origin_not_ready')
    row = copy.deepcopy(origin)
    if spec['kind'] == 'trace_derived_control':
        row['operation']['content'] = spec['content']
        row['operation']['content_sha256'] = old.digest(spec['content'])
        derived_id = 'benchmark:'+ci.identity({'content':spec['content'],'evidence':spec['evidence']})
        row['operation']['revision_id'] = derived_id
        row['operation']['memory_id'] = derived_id
        citations = [quoted_source(packet, s) for s in spec['evidence']]
        for i, item in enumerate(citations): item['citation_index'] = i
        row['preparation']['citations'] = citations
    else:
        old.require(spec['kind'] == 'historical_original', 'unknown_case_kind')
    # Real production renderer is used without editing its prompt/schema/system.
    original_material = cr.projection(packet, origin)
    material = cr.projection(packet, row)
    request = copy.deepcopy(cr.requests(packet)[spec['op_index']]['request'])
    before = json.dumps(original_material, ensure_ascii=False)
    after = json.dumps(material, ensure_ascii=False)
    old.require(request['prompt'].count(before) == 1, 'production_template_drift')
    request['prompt'] = request['prompt'].replace(before, after, 1)
    request['audit_request_sha256'] = ci.identity({k: request[k] for k in ('system','prompt','tools')})
    sources = [c['candidates'][0]['reference'] for c in row['preparation']['citations']]
    case = {'sample_id': spec['id'], 'kind': spec['kind'], 'origin': {
        'commit': SOURCE_COMMIT, 'slot_path': (ROOT/old.SAMPLES[spec['sample']][0]).as_posix(),
        'step': spec['step'], 'cycle_id': packet['cycle_id'], 'operation': spec['op_index'],
        'revision_id': origin['operation']['revision_id'], 'parent_input_sha256': packet['citation_input_sha256']},
        'material': material, 'citations': sources, 'request': request}
    case['benchmark_input_sha256'] = ci.identity(case)
    return validate_case(case)


def expected_request(material):
    """Closed renderer matching pinned production requests; no appended instructions."""
    old.require(isinstance(material,dict) and set(material)=={
        'original_operation','submitted_evidence','normative_requirements_context'}, 'material_schema')
    op=material['original_operation']; evidence=material['submitted_evidence']
    old.require(isinstance(op,dict) and set(op)=={
        'op_index','action','memory_id','revision_id','content','content_sha256'}, 'operation_schema')
    old.require(type(op['op_index']) is int and op['op_index']>=0, 'operation_index')
    old.require(all(isinstance(op[k],str) and op[k] for k in
        ('action','memory_id','revision_id','content','content_sha256')), 'operation_fields')
    old.require(op['content_sha256']==old.digest(op['content']), 'operation_content_hash')
    old.require(material['normative_requirements_context']=='', 'benchmark_normative_context')
    old.require(isinstance(evidence,list) and bool(evidence), 'evidence_empty')
    for i,item in enumerate(evidence):
        old.require(isinstance(item,dict) and set(item)=={
            'evidence_id','submitted_quote','role','field_path','source_id','event_order',
            'source_identity_origin'}, 'evidence_schema')
        old.require(item['evidence_id']=='E'+str(i+1) and
            item['source_identity_origin']=='host_inferred_not_model_selected', 'evidence_identity')
        old.require(all(isinstance(item[k],str) and item[k] for k in
            ('submitted_quote','role','field_path','source_id')), 'evidence_fields')
        old.require(type(item['event_order']) is int and item['event_order']>=0, 'evidence_order')
        old.require(item['role'] in {'task_instruction','tool_command','tool_observation',
            'agent_report','memory_derived'}, 'evidence_role')
    prompt='SUBMITTED OPERATION AND CLOSED EVIDENCE PACKAGE:\n'+json.dumps(material,ensure_ascii=False)
    prompt+='\nOUTPUT EXAMPLE (shape only; decide from submitted quotes):\n'+json.dumps({
        'op_index':op['op_index'],'verdict':'insufficient',
        'explanation':'Explain which commitments the submitted evidence establishes or leaves unsupported.'})
    payload={'system':cr.SYSTEM,'prompt':prompt,'tools':None}
    return {'phase':'audit_submitted_citations',**payload,'op_index':op['op_index'],
        'review_strategy':cr.STRATEGY,'evidence_policy':'submitted-literal-only-v1',
        'audit_request_sha256':ci.identity(payload)}


def validate_case(case):
    old.require(case['benchmark_input_sha256']==ci.identity({k:v for k,v in case.items()
                if k!='benchmark_input_sha256'}), 'benchmark_input_hash')
    expected=expected_request(case['material'])
    old.require(case['request']==expected and ci.identity(case['request'])==ci.identity(expected),
                'noncanonical_request')
    return case


def load_dataset(path, expected_manifest_sha256, *, include_evaluation=False):
    """Pin must come from the reviewed handoff, not from the dataset being checked."""
    root=Path(path);raw=(root/'MANIFEST.json').read_bytes()
    old.require(hashlib.sha256(raw).hexdigest()==expected_manifest_sha256, 'frozen_manifest_mismatch')
    manifest=ci.strict_json(raw.decode('utf-8'))
    old.require(manifest.get('schema')=='citation-benchmark-development-v1' and
        manifest.get('code_sha')==CODE_COMMIT and manifest.get('source_sha')==SOURCE_COMMIT and
        manifest.get('split')=='development_only_two_tasks', 'manifest_contract')
    old.require(set(manifest['files'])=={'cases.json','evaluation-only.json','inventory.json','requests.json'},
                'manifest_file_set')
    documents={}
    for name,digest in manifest['files'].items():
        data=(root/name).read_bytes()
        old.require(hashlib.sha256(data).hexdigest()==digest, 'manifest_hash')
        if include_evaluation or name in {'cases.json','requests.json'}:
            documents[name]=ci.strict_json(data.decode('utf-8'))
    cases=documents['cases.json'];ids=[c['sample_id'] for c in cases]
    old.require(len(ids)==len(set(ids)), 'duplicate_sample')
    for case in cases: validate_case(case)
    old.require(documents['requests.json']==[{'sample_id':c['sample_id'],**c['request']} for c in cases],
                'export_request_mismatch')
    return documents


async def run(dataset, transport, *, expected_manifest_sha256, sample_ids=None, on_result=None):
    """Public runner always checks the externally pinned manifest before any call."""
    cases=load_dataset(dataset,expected_manifest_sha256)['cases.json']
    if sample_ids is not None:
        old.require(len(sample_ids)==len(set(sample_ids)) and
            set(sample_ids)<=set(c['sample_id'] for c in cases), 'selected_sample_ids')
        cases=[c for c in cases if c['sample_id'] in sample_ids]
    return await _run_validated_cases(cases,transport,on_result=on_result)


async def _run_validated_cases(cases, transport, *, on_result=None):
    """Production transport + strict production response parser; labels never consumed."""
    results=[]; stopped=False
    for case in cases:
        validate_case(case)
        result={'sample_id':case['sample_id'], 'benchmark_input_sha256':case['benchmark_input_sha256'],
                'audit_request_sha256':case['request']['audit_request_sha256'],
                'verdict':None,'model_verdict':None,'raw_response':None}
        if stopped:
            result['engineering_status']='not_run_after_engineering_error'
            results.append(result)
            if on_result is not None: on_result(result)
            continue
        try:
            raw=await transport.send(case['request']); result['raw_response']=raw
        except ResponseProtocolError as e:
            result.update(engineering_status='protocol_error',raw_response=e.raw_response,reason=e.code)
            try:
                value=cr.json_value(e.raw_response)
                if isinstance(value,dict):result['model_verdict']=value.get('verdict')
            except (ValueError,TypeError):pass
        except Exception as e:
            result.update(engineering_status='call_error',error_type=type(e).__name__)
        else:
            try:
                value=cr.json_value(raw)
                if isinstance(value,dict): result['model_verdict']=value.get('verdict')
                result.update(cr.parse(value,case['request']['op_index']),engineering_status='ok')
            except (ValueError,KeyError,TypeError) as e:
                result.update(engineering_status='parse_failure',reason=str(e))
        results.append(result)
        if on_result is not None: on_result(result)
        stopped=result['engineering_status']!='ok'
    return results


def score(cases, labels, results):
    by_case={c['sample_id']:c for c in cases};ids=list(by_case)
    old.require(len(ids)==len(cases), 'duplicate_sample')
    old.require(set(labels)==set(ids), 'label_sample_set')
    by_id={}
    for result in results:
        sid=result['sample_id']
        old.require(sid in ids and sid not in by_id, 'unknown_or_duplicate_result')
        case=by_case[sid]
        old.require(result.get('benchmark_input_sha256')==case['benchmark_input_sha256'] and
                    result.get('audit_request_sha256')==case['request']['audit_request_sha256'],
                    'result_request_identity_mismatch')
        by_id[sid]=result

    def summarize(selected):
        matrix={a:{b:0 for b in LABELS} for a in LABELS}
        missing=[];errors=[];not_run=[];valid=0
        for sid in selected:
            old.require(labels[sid]['reference_label'] in LABELS, 'reference_label')
            if sid not in by_id: missing.append(sid);continue
            row=by_id[sid]
            if row.get('engineering_status')=='not_run_after_engineering_error':
                not_run.append(sid);continue
            if row.get('engineering_status')!='ok' or row.get('verdict') not in LABELS:
                errors.append(sid);continue
            valid+=1;matrix[labels[sid]['reference_label']][row['verdict']]+=1
        return {'confusion_matrix':matrix,'total_samples':len(selected),'valid_samples':valid,
                'engineering_error_count':len(errors),'engineering_errors':errors,
                'missing_result_count':len(missing),'missing_results':missing,
                'not_run_count':len(not_run),'not_run':not_run}

    def endpoint(sid):
        row=by_id.get(sid,{})
        valid=row.get('engineering_status')=='ok' and row.get('verdict') in LABELS
        return {'sample_id':sid,'reference_label':labels[sid]['reference_label'],
                'verdict':row.get('verdict'),'engineering_status':row.get('engineering_status','missing'),
                'matches_reference':row['verdict']==labels[sid]['reference_label'] if valid else None}

    pairs=[]
    for sid in ids:
        partner=labels[sid].get('matched_pair')
        if partner is None: continue
        old.require(partner in by_case and partner!=sid and
            by_case[partner]['material']['original_operation']['content']==
            by_case[sid]['material']['original_operation']['content'], 'matched_pair_conclusion')
        strong,weak=endpoint(partner),endpoint(sid)
        matches=[strong['matches_reference'],weak['matches_reference']]
        pairs.append({'reference_partner':strong,'evidence_changed_case':weak,
                      'both_match_reference':all(matches) if None not in matches else None})
    report=summarize(ids)
    report['strata']={kind:summarize([sid for sid in ids if by_case[sid]['kind']==kind])
                     for kind in ('historical_original','trace_derived_control')}
    report['same_conclusion_pairs']=pairs
    report['note']='Development reference judgments, not external gold; preparation skips reported separately.'
    return report


def build(repo, specs, out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    audit,packets=inventory(repo)
    cases=[];labels={}
    for spec in specs:
        case=build_case(spec,packets[f"{spec['sample']}-{spec['step']}"]);cases.append(case)
        labels[spec['id']]={k:spec[k] for k in ('reference_label','reason','family','kind','change')}
        if 'matched_pair' in spec: labels[spec['id']]['matched_pair']=spec['matched_pair']
    old.require(len(labels)==len(cases),'duplicate_sample')
    selected={(s['sample'],s['step'],s['op_index']) for s in specs if s['kind']=='historical_original'}
    audit['eligible_not_in_main']=[]
    for key,packet in packets.items():
        sample,step=key.rsplit('-',1)
        for row in packet['operations']:
            if row['preparation']['status']=='ready' and (sample,int(step),row['operation']['op_index']) not in selected:
                audit['eligible_not_in_main'].append({'sample':sample,'step':int(step),
                    'op_index':row['operation']['op_index'],'revision_id':row['operation']['revision_id'],
                    'reason':'Unresolved plan/inference/scope ambiguity; no main reference label assigned.'})
    write(out/'cases.json',cases);write(out/'evaluation-only.json',labels);write(out/'inventory.json',audit)
    write(out/'requests.json',[{'sample_id':c['sample_id'],**c['request']} for c in cases])
    write(out/'MANIFEST.json',{'schema':'citation-benchmark-development-v1','code_sha':CODE_COMMIT,
        'source_sha':SOURCE_COMMIT,'split':'development_only_two_tasks',
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir())}})
    return cases,labels,audit
