"""Host-only recovery/validation of submitted quotes; model projection lives elsewhere."""
import copy
import hashlib
import json
from pathlib import Path

from . import inputs as old

SCHEMA = 'pma-submitted-citation-input-v1'
WRITERS = {'update_status','save_knowledge','save_procedural','save_gap'}
LIMIT = 'Recovered alignment items, not original tool arguments; missing/empty/malformed arguments may be unrecoverable.'


def identity(value):
    return old.digest(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')))


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            old.require(key not in result, 'duplicate_alignment_key')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs)


def candidate(ref, parent, source_records=None):
    """Validate only manifest-visible bytes. Never fetch a full/final source."""
    old.require(isinstance(ref,dict) and set(ref) <= {
        'source_id','source_kind','role','order','start','end','source_text_sha256',
        'snippet_sha256','visibility_ref','parent_revision_id','parent_wrapper_source_id'}, 'candidate_shape')
    old.require(type(ref.get('order')) is int, 'candidate_order_type')
    source=old.only(parent['sources'],lambda s:s['source_id']==ref.get('source_id'),'candidate_source_not_visible')
    for field,key in [('role','role'),('order','event_order'),('visibility_ref','visibility_ref')]:
        old.require(ref.get(field)==source[key],'candidate_'+field+'_mismatch')
    old.require(ref.get('source_kind')==source['kind'],'candidate_kind_mismatch')
    sid = json.loads(source['source_id'])
    revision = ref.get('parent_revision_id')
    if source['kind'] == 'public':
        old.require(revision is None, 'public_parent_revision_forbidden')
    else:
        old.require(revision == sid[2] and revision in parent['manifest']['pre_cycle_revision_refs']
                    and source['role'] == 'memory_derived' and source['field_path'] == 'content',
                    'memory_parent_revision_mismatch')
    wrapper = ref.get('parent_wrapper_source_id')
    if wrapper is not None:
        old.require(isinstance(wrapper, str), 'wrapper_type')
        w = strict_json(wrapper)
        old.require(source['kind'] == 'public' and isinstance(w,list) and len(w)==4
                    and w[:3] == sid[:3] and isinstance(w[3],str)
                    and source['field_path'].startswith(w[3]+'/'), 'wrapper_identity')
    start,end=ref.get('start'),ref.get('end')
    old.require(type(start) is int and type(end) is int and 0<=start<end,'candidate_coordinates')
    piece=old.only(source['slices'],lambda s:s['start']<=start<end<=s['end'],'candidate_outside_visible_span')
    excerpt=piece['text'][start-piece['start']:end-piece['start']]
    old.require(old.digest(excerpt)==ref.get('snippet_sha256'),'candidate_snippet_hash')
    source_hash=ref.get('source_text_sha256')
    old.require(isinstance(source_hash,str) and len(source_hash)==64 and
                all(c in '0123456789abcdef' for c in source_hash),'candidate_source_hash_shape')
    check = 'full_source_unavailable_not_asserted'
    record = (source_records or {}).get(source['source_id'])
    if record is not None:
        for field,key in [('source_kind','kind'),('role','role'),('order','event_order'),
                          ('field_path','field_path'),('source_id','source_id')]:
            old.require(record.get(field)==source[key], 'source_record_identity')
        old.require(record.get('parent_revision_id')==revision and
                    record.get('parent_wrapper_source_id')==wrapper, 'source_record_parent')
        old.require(record.get('text_sha256')==source_hash, 'candidate_source_hash_mismatch')
        check = 'matches_verified_source_record'
    elif piece['start']==0 and old.digest(piece['text'])==source_hash:
        check = 'matches_visible_text'
    return {'reference':copy.deepcopy(ref),'original_excerpt':excerpt,
        'field_path':source['field_path'],'handle':source['handle'],
        'source_text_hash_check':check,
        'coordinate_unit':'python_unicode_code_points','binding_origin':'host_inferred_not_model_selected'}


def prepare(op, alignment, parent, source_records=None):
    records,issues=[],[]
    if not op['success']:
        return {'status':'not_reviewed_failed_operation','issues':[],'citations':[]}
    if op['action']=='delete' or op['action'].startswith('delete_'):
        return {'status':'not_applicable_delete_protocol','issues':['delete_accepts_only_memory_id'], 'citations':[]}
    if op['action'] not in WRITERS:
        return {'status':'not_reviewed_unknown_action','issues':[],'citations':[]}
    if alignment is None:
        return {'status':'evidence_unavailable','issues':['alignment_missing_original_arguments_unavailable'],'citations':[]}
    if not isinstance(alignment,dict):
        return {'status':'malformed_evidence_unavailable','issues':['alignment_shape'],'citations':[]}
    if alignment.get('revision_id')!=op['revision_id'] or alignment.get('cycle_id')!=parent['cycle_id']:
        return {'status':'identity_mismatch','issues':['alignment_cycle_or_revision_mismatch'],'citations':[]}
    try:
        data=strict_json(alignment['alignment_json'])
        old.require(isinstance(data,dict) and isinstance(data.get('items'),list)
                    and isinstance(data.get('bound_refs'),list)
                    and isinstance(data.get('status'),str)
                    and (data.get('reason') is None or isinstance(data['reason'],str)), 'alignment_items')
        for item in data['items']:
            old.require(isinstance(item,dict) and isinstance(item.get('quote'),str)
                        and isinstance(item.get('candidates'),list) and isinstance(item.get('status'),str)
                        and (item.get('source_hint') is None or
                             isinstance(item['source_hint'],str) and bool(item['source_hint']))
                        and (item.get('reason') is None or isinstance(item['reason'],str))
                        and isinstance(item.get('metadata',{}),dict), 'alignment_item_types')
    except (ValueError,TypeError,KeyError):
        return {'status':'malformed_evidence_unavailable','issues':['alignment_json_or_items_malformed'],'citations':[]}
    if not data['items']:
        status='no_evidence' if data.get('reason')=='no_evidence' else 'malformed_evidence_unavailable'
        return {'status':status,'issues':['no_recoverable_items_missing_vs_empty_unknown'],'citations':[]}
    for index,item in enumerate(data['items']):
        row={'citation_index':index,'submitted_record':copy.deepcopy(item),'candidates':[],'issues':[]}
        records.append(row)
        if not isinstance(item,dict) or not isinstance(item.get('quote'),str) or not item['quote'].strip() or not isinstance(item.get('candidates'),list):
            row['issues'].append('malformed_submitted_record')
            continue
        row.update(submitted_quote=item['quote'],source_hint=item.get('source_hint'),binding_status=item.get('status'))
        if item.get('status')!='exact_unique':
            row['issues'].append('binding_'+str(item.get('status','missing')))
        if len(item['candidates'])!=1:
            row['issues'].append('candidate_count_'+str(len(item['candidates'])))
        for ref in item['candidates']:
            try:
                bound=candidate(ref,parent,source_records)
                row['candidates'].append(bound)
                if item['quote']!=bound['original_excerpt']:
                    row['issues'].append('quote_differs_from_visible_excerpt')
            except (ValueError,TypeError,KeyError) as error:
                row['candidates'].append({'reference':copy.deepcopy(ref),'validation_error':str(error)})
                row['issues'].append('candidate_integrity_error')
    flattened=[]
    for item in data['items']:
        for ref in item['candidates']:
            if ref not in flattened: flattened.append(ref)
    if flattened != data['bound_refs']:
        issues.append('aggregate_bound_refs_mismatch')
    if data.get('status')!='exact_unique' or alignment.get('status')!='exact_unique':
        issues.append('operation_binding_not_exact_unique')
    issues += ['citation_%s:%s'%(row['citation_index'],code) for row in records for code in row['issues']]
    return {'status':'ready' if not issues else 'citation_set_not_eligible','issues':issues,'citations':records}


def build_from_parent(parent, alignments, *, normative_context='', source_records=None):
    old.validate(parent)
    old.require(isinstance(normative_context,str) and (not normative_context or
                normative_context in parent['original_task']),'normative_context_not_task_excerpt')
    operations=[]
    for op in old.model_material(parent)['operations']:
        # A delete revision points to the OLD write. Never borrow that write's citations.
        raw=None if op['action']=='delete' or op['action'].startswith('delete_') or not op['success'] else alignments.get(op.get('revision_id'))
        operations.append({'operation':op,'recovered_alignment':copy.deepcopy(raw),
                           'preparation':prepare(op,raw,parent,source_records)})
    packet={'schema':SCHEMA,'cycle_id':parent['cycle_id'],'step':parent['step'],
        'call_sequence':parent['call_sequence'],'parent_input_sha256':parent['review_input_sha256'],
        'host_provenance':copy.deepcopy(parent),'host_provenance_sha256':identity(parent),
        'source_records':copy.deepcopy(source_records or {}),'normative_context':normative_context,'recovery_limitations':[LIMIT], 'operations':operations}
    packet['citation_input_sha256']=identity(packet)
    return validate(packet)


def validate(packet):
    old.require(packet.get('schema')==SCHEMA,'citation_schema')
    old.require(packet.get('citation_input_sha256')==identity({k:v for k,v in packet.items()
                if k!='citation_input_sha256'}),'citation_input_hash')
    parent=old.validate(packet['host_provenance'])
    old.require(packet['host_provenance_sha256']==identity(parent),'host_provenance_hash')
    for key in ('cycle_id','step','call_sequence'):
        old.require(packet[key]==parent[key],'parent_'+key+'_mismatch')
    old.require(packet['parent_input_sha256']==parent['review_input_sha256'],'parent_input_mismatch')
    context=packet['normative_context']
    old.require(isinstance(context,str) and (not context or context in parent['original_task']), 'normative_context_not_task_excerpt')
    original=old.model_material(parent)['operations']
    old.require(len(packet['operations'])==len(original),'citation_operation_count')
    for row,op in zip(packet['operations'],original):
        old.require(row['operation']==op,'citation_operation_identity')
        old.require(row['preparation']==prepare(op,row['recovered_alignment'],parent,packet.get('source_records',{})),'citation_preparation_mismatch')
    return packet


def build(repo,sample):
    """Archive adapter: checked files + exact historical revision, never active bank."""
    slot,step,cycle=old.SAMPLES[sample]
    parent=old.build(repo,sample)  # verifies global/slot/gzip/uncompressed identity and chains
    path=Path(repo)/old.D/'source_window_two_real_20261025'/slot
    files=json.loads((path/'INDEX.json').read_text(encoding='utf-8'))['files']
    bank=old.load_indexed(path/'memory.json.gz',files)
    # Retained records are optional historical integrity witnesses, never model evidence.
    # Validate available full blobs locally; only metadata hashes enter the packet.
    store=bank['gap_evidence']; records={}
    for source in parent['sources']:
        record=store['sources'].get(source['source_id'])
        if record is None: continue
        text=store['blobs'].get(record['text_sha256'])
        old.require(isinstance(text,str) and old.digest(text)==record['text_sha256'], 'source_blob_hash')
        old.require(all(text[p['start']:p['end']]==p['text'] for p in source['slices']), 'source_blob_visible_mismatch')
        records[source['source_id']]=record
    return build_from_parent(parent,bank.get('gap_alignment',{}).get('alignments',{}),source_records=records)
