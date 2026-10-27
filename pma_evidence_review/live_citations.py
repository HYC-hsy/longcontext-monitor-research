"""Live candidate envelope, never an archive reconstruction or a memory publisher."""
from dataclasses import asdict
import copy

from . import citation_inputs as ci, citation_review as cr
from .prompt_strategy import ONE_SENTENCE, apply_strategy
from .transport import ResponseProtocolError


def build_live(draft, parts, operation, index, *, run_id):
    # Host snapshots and validation stay outside the model projection.
    draft.validate_bank()
    revision=draft.revisions[operation.revision_id]
    content=draft._content(operation.memory_id)[1]
    ci.old.require(content==operation.content, 'candidate_content_changed')
    ci.old.require(revision.content_sha256==ci.old.digest(content), 'candidate_revision_content')
    parent,records=visible_snapshot(parts)
    op={'op_index':index,'action':operation.action,'memory_id':operation.memory_id,
        'revision_id':operation.revision_id,'content':content,'content_sha256':ci.old.digest(content),
        'success':True}
    alignment=asdict(draft.alignments[operation.revision_id])
    preparation=ci.prepare(op,alignment,parent,records)
    envelope={'schema':'pma-live-citation-candidate-v1','run_id':run_id,
        'cycle_id':parts.manifest.cycle_id,'maintenance_request_sha256':parts.manifest.request_sha256,
        'operation':op,'previous_revision_id':revision.previous_revision_id,
        'host_provenance':parent,'source_records':records,'alignment':alignment,
        'preparation':preparation,'normative_context':''}
    envelope['live_input_sha256']=ci.identity(envelope)
    row={'operation':op,'preparation':preparation}
    request=None
    if preparation['status']=='ready':
        request=apply_strategy(cr.request_from_material(cr.projection(envelope,row),index),ONE_SENTENCE)
    return envelope,request


async def assess(request,transport):
    result={'verdict':None,'model_verdict':None,'raw_response':None,'engineering_status':'received'}
    try:
        result['raw_response']=await transport.send(copy.deepcopy(request))
    except ResponseProtocolError as error:
        result.update(engineering_status='protocol_error',reason=error.code,raw_response=error.raw_response)
    except Exception as error:
        result.update(engineering_status='call_error',error_type=type(error).__name__)
    if result['raw_response'] is not None:
        try:
            data=cr.json_value(result['raw_response'])
            if isinstance(data,dict):result['model_verdict']=data.get('verdict')
            if result['engineering_status']=='received':
                result.update(cr.parse(data,request['op_index']),engineering_status='ok')
        except (ValueError,TypeError,KeyError) as error:
            if result['engineering_status']=='received':
                result.update(engineering_status='parse_failure',reason=str(error))
    return result


def visible_snapshot(parts):
    sources=[];records={}
    for visible in parts.catalog.values():
        record=visible.snapshot.record
        sources.append({'source_id':record.source_id,'handle':record.handle,
            'kind':record.source_kind,'role':record.role,'event_order':record.order,
            'field_path':record.field_path,'visibility_ref':visible.visibility_ref,
            'slices':[{'start':a,'end':b,'text':visible.snapshot.blob.text[a:b]}
                      for a,b in visible.visible_spans]})
        records[record.source_id]=asdict(record)
    parent={'cycle_id':parts.manifest.cycle_id,'manifest':asdict(parts.manifest),'sources':sources}
    return parent,records
