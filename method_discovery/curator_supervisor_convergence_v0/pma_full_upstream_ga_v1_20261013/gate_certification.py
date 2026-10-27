"""Strict synthetic gate lifecycle evidence; supplements native Harbor certification.
No model/client/profile imports or execution. A certificate is an evidence index,
not a signature: its observations are revalidated from the committed raw files.
"""
import hashlib
import json
from pathlib import Path

from .citation_gate_config import MODES, verify_gate_sources, gate_source_paths
from pma_evidence_review import citation_inputs as ci, citation_review as cr
from pma_evidence_review.inputs import require, digest
from pma_evidence_review.prompt_strategy import apply_strategy, ONE_SENTENCE
from pma_evidence_review.gate_control import receipt, REPAIR_SYSTEM

FILES=('execution_identity.json','memory_payload.jsonl','gap_visible_transport.jsonl',
       'gap_cycle.jsonl','memory.json')
SCHEMA='pma-gate-lifecycle-certificate-v1'


def source_paths():
    stage=Path(__file__).resolve().parent
    root=stage.parents[2]
    return sorted(set(gate_source_paths()+[(stage/n).relative_to(root).as_posix() for n in (
        'gate_certification.py','single_run_fixture.py','collect_single_run_fixture.py',
        'single_run_certification.py','worker_main.py','prepare_six_task_manifest.py',
        'live_launcher.py','pma_harbor_hooks.py')]))


def source_identity():
    from .prepare_six_task_manifest import _committed_source_sha
    root=Path(__file__).resolve().parent.parents[2]
    return {p:_committed_source_sha(root,p) for p in source_paths()}


def _rows(path):
    return [ci.strict_json(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]


def _payload(row):
    return {k:row[k] for k in ('system','prompt','tools')}


def inspect_evidence(base, mode):
    require(mode in MODES,'gate_certificate_mode')
    base=Path(base)
    execution=ci.strict_json((base/'execution_identity.json').read_text(encoding='utf-8'))
    config=execution.get('gate_config',{})
    require(config.get('citation_review_gate')==mode,'gate_execution_mode')
    verify_gate_sources(config)
    require(execution.get('gate_certificate_source_sha256')==source_identity(),'gate_certificate_source_identity')
    requests=_rows(base/'memory_payload.jsonl');responses=_rows(base/'gap_visible_transport.jsonl')
    require([r['call_sequence'] for r in requests]==list(range(1,len(requests)+1)),'gate_call_sequence')
    require([r['call_sequence'] for r in responses]==[r['call_sequence'] for r in requests],'gate_response_sequence')
    for q,a in zip(requests,responses):
        require((q['phase'],q['cycle_step'])==(a['phase'],a['cycle_step']),'gate_response_phase')
    cycles=_rows(base/'gap_cycle.jsonl')
    # Only maintenance cycles; event logs may include task_end with no report.
    cycles=[r for r in cycles if r.get('citation_gate_report')]
    groups=[]
    for q,a in zip(requests,responses):
        if q['phase']=='maintenance':groups.append([])
        require(bool(groups),'gate_missing_maintenance')
        groups[-1].append((q,a))
    require(len(groups)==len(cycles) and len(groups)>=2,'gate_next_maintenance_required')
    bank=ci.strict_json((base/'memory.json').read_text(encoding='utf-8'))
    # Canonical bank loader validates revisions, active identity and source linkage.
    from .single_run_certification import require_bound_gap_memory
    require_bound_gap_memory(base/'memory.json')
    from latest_evidence_gap_store import LatestEvidenceGapMemory
    loaded=LatestEvidenceGapMemory.from_dict(bank)
    accepted=[];rejected=[];pending=None;repairs=0;delivered=0
    for group,cycle in zip(groups,cycles):
        report=cycle['citation_gate_report'];visibility=report['frozen_visibility']
        manifest=visibility['manifest'];cid=manifest['cycle_id']
        require(report['strategy']==ONE_SENTENCE and report['repair_limit']==int(mode=='gate-one-repair'),
                'gate_report_strategy')
        require(not report['incomplete'],'gate_report_incomplete')
        maintenance,answer=group[0];selection=group[-1][0]
        require(maintenance['phase']=='maintenance' and selection['phase']=='selection','gate_phase_edges')
        require(digest(maintenance['prompt'])==manifest['request_sha256'],'gate_maintenance_hash')
        parsed=ci.old.visible_sources(maintenance['prompt'],manifest)
        def source_projection(source):
            return {k:v for k,v in source.items() if k!='handle' or source['kind']=='public'}
        require([source_projection(x) for x in parsed]==[source_projection(x) for x in visibility['sources']],
                'gate_visible_registry_mismatch')
        require(answer['content']==report['raw_response_phase1'],'gate_phase1_response')
        if pending is not None:
            marker='HOST COMMIT RECEIPT — CONTROL ONLY (not a source; proposals are not commits):\n'
            require(marker in maintenance['prompt'],'gate_receipt_not_sent')
            sent=ci.strict_json(maintenance['prompt'].split(marker,1)[1])
            require(sent==pending,'gate_receipt_payload')
            deliveries=[x for x in report['prior_receipt_deliveries'] if x['receipt_id']==pending['receipt_id']]
            require(len(deliveries)==1 and deliveries[0]['status']=='response_received_consumed'
                    and deliveries[0]['maintenance_request_sha256']==manifest['request_sha256'],'gate_receipt_not_delivered')
            require(bool(answer.get('content') or answer.get('tool_calls')),'gate_receipt_empty_response')
            delivered+=1
        # Explicit source registry, not full prompt substring matching.
        for source in visibility['sources']:
            require(source['kind']=='public' or source['role']=='memory_derived','gate_source_kind')
            if source['kind']=='public':
                require(source['role'] in ('task_instruction','agent_report','tool_command','tool_observation'),
                        'gate_control_registered_as_source')
            for piece in source['slices']:
                require('GATE_FIXTURE_REVIEW_CONTROL_ONLY' not in piece['text']
                        and 'HOST COMMIT RECEIPT' not in piece['text']
                        and 'GATE_FIXTURE_REJECTED' not in piece['text'],'gate_control_source_leak')
        require('HOST COMMIT RECEIPT' not in selection['prompt'] and
                'GATE_FIXTURE_REJECTED' not in selection['prompt'],'gate_selection_leak')
        expected=[]
        rows=report['operations']
        require([r['index'] for r in rows]==list(range(len(rows))),'gate_operation_indices')
        for row in rows:
            require(row['cycle_id']==cid,'gate_operation_cycle')
            attempts=row.get('attempts',[])
            require(1<=len(attempts)<=1+report['repair_limit'],'gate_attempt_count')
            current=row['submitted_arguments']
            for number,attempt in enumerate(attempts):
                require(attempt['attempt']==number,'gate_attempt_order')
                env=attempt['input'];op=env['operation']
                require(env['cycle_id']==cid and env['host_provenance']==visibility,'gate_frozen_visibility')
                require(env['live_input_sha256']==ci.identity({k:v for k,v in env.items() if k!='live_input_sha256'}),
                        'gate_live_input_hash')
                require(op['content']==current['content'] and row['tool']=='memory_'+op['action'], 'gate_proposed_content')
                require(current.get('memory_id') in (None,op['memory_id']), 'gate_fixed_target')
                alignment=ci.strict_json(env['alignment']['alignment_json'])
                require([(x['quote'],x['source_hint']) for x in alignment['items']]==
                        [(x['quote'],x.get('source')) for x in current['evidence']], 'gate_submitted_citations')
                require(op['op_index']==row['index'] and digest(op['content'])==op['content_sha256'],
                        'gate_operation_identity')
                prep=ci.prepare(op,env['alignment'],visibility,env['source_records'])
                require(prep==env['preparation'] and prep['status']=='ready','gate_preparation')
                request=apply_strategy(cr.request_from_material(cr.projection(env,{'operation':op,'preparation':prep}),row['index']),ONE_SENTENCE)
                require(request==attempt['request'],'gate_request_projection')
                verdict=cr.parse(cr.json_value(attempt['raw_response']),row['index'])
                require(attempt['engineering_status']=='ok' and verdict['verdict']==attempt['verdict'],'gate_verdict')
                expected.append(('citation_review',request,attempt['raw_response']))
                if number==0 and row.get('repair'):
                    repair=row['repair'];req=repair['request'];repairs+=1
                    require(mode=='gate-one-repair' and attempt['verdict']!='supported','gate_repair_eligibility')
                    require(repair['engineering_status']=='ok' and req['system']==REPAIR_SYSTEM and req['tools'] is None,
                            'gate_repair_contract')
                    mat=ci.strict_json(req['prompt'])
                    require(mat['original_maintenance_material']==maintenance['prompt'] and
                            mat['original_arguments']==row['submitted_arguments'] and mat['fixed_tool']==row['tool'],
                            'gate_repair_fixed_target')
                    require(req['audit_request_sha256']==ci.identity(_payload(req)),'gate_repair_request_hash')
                    require(ci.strict_json(repair['raw_response'])==repair['replacement'],'gate_repair_response')
                    value=repair['replacement']
                    if value.get('decision')=='withdraw':
                        require(set(value)=={'decision'} and len(attempts)==1 and row.get('withdrawn') is True,
                                'gate_withdraw_contract')
                    else:
                        require(set(value)=={'decision','content','evidence'} and value['decision']=='replace'
                                and len(attempts)==2, 'gate_replace_contract')
                        current={**current,'content':value['content'],'evidence':value['evidence']}
                    expected.append(('citation_repair',req,repair['raw_response']))
            last=attempts[-1];op=last['input']['operation'];rid=op['revision_id']
            if row['success']:
                require(last['verdict']=='supported' and row['content_status']=='committed','gate_unreviewed_publish')
                revision=loaded.revisions.get(rid)
                require(revision is not None and revision.content_sha256==op['content_sha256'], 'gate_committed_revision')
                require(loaded.active_revisions.get(op['memory_id'])==rid,'gate_final_bank')
                accepted.append(rid)
            else:
                require(last['verdict']!='supported' and row['content_status']=='not_committed','gate_rejection_state')
            for attempt in attempts:
                rid=attempt['input']['operation']['revision_id']
                if rid not in accepted:
                    require(rid not in loaded.revisions,'gate_rejected_revision_published');rejected.append(rid)
        actual=group[1:-1]
        require(len(actual)==len(expected),'gate_phase_count')
        for (q,a),(phase,req,raw) in zip(actual,expected):
            require(q['phase']==phase and _payload(q)==_payload(req) and a['content']==raw
                    and not a.get('tool_calls'),'gate_actual_call_mismatch')
        if rows:
            pending=receipt(cid,rows)
            require(pending==report['final_receipt'],'gate_receipt_reconstruction')
        else:
            require(report['final_receipt'] is None,'gate_stale_receipt')
            pending=None
    require(accepted and rejected and delivered and pending is None,'gate_fixture_coverage')
    require((repairs>0)==(mode=='gate-one-repair'),'gate_repair_coverage')
    return {'schema':SCHEMA,'mode':mode,'source_sha256':source_identity(),
            'evidence_sha256':{n:hashlib.sha256((base/n).read_bytes()).hexdigest() for n in FILES},
            'accepted_revisions':accepted,'rejected_revisions':rejected,'receipts_delivered':delivered,'repair_calls':repairs}


def verify_certificate(base,mode):
    expected=inspect_evidence(base,mode)
    supplied=ci.strict_json((Path(base)/'gate_certificate.json').read_text(encoding='utf-8'))
    require(supplied==expected,'gate_certificate_mismatch')
    return expected


def require_launch_certificate(manifest, *, fixture=False):
    mode=manifest.get('config',{}).get('citation_review_gate')
    if mode is None:return
    require(mode in MODES,'gate_launch_mode')
    if fixture:
        require(manifest.get('zero_model_fixture_only') is True,'gate_fixture_identity')
        return
    certification=manifest.get('native_shared_certification') or {}
    root=Path(__file__).resolve().parent.parents[2]
    relative=certification.get('evidence_path')
    require(isinstance(relative,str),'gate_certificate_required')
    base=(root/relative).resolve(strict=True)
    require(base.is_relative_to(root),'gate_certificate_outside_repository')
    from .single_run_certification import _committed_evidence_sha
    for name in (*FILES,'gate_certificate.json'):
        _committed_evidence_sha(root,base/'B'/name)
    actual=verify_certificate(base/'B',mode)
    require(certification.get('evidence',{}).get('gate_certificate')==actual,'gate_manifest_certificate')


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Verify committed native Harbor plus gate lifecycle evidence; no execution.')
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--mode',choices=MODES,required=True)
    args=parser.parse_args()
    from .single_run_certification import verify_evidence
    result=verify_evidence(args.evidence,research_candidate='pma_gap_evidence_v1',citation_review_gate=args.mode)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))


if __name__=='__main__':main()
