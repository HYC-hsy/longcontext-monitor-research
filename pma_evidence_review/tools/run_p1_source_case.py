"""One frozen P1 case only. Scripted by default; real mode needs later authorization."""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]
REL = 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
STAGE = ROOT / REL
for path in (ROOT, STAGE / 'vendor/pma_89e5c0d/external/harbor/src',
             STAGE / 'vendor/pma_89e5c0d/src', STAGE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from bank_display_agent import BankDisplayAgent
from p1_source_agent import SourceReadP1Agent, SYSTEM, READ_LIMIT, CONTINUATION_LIMIT
from p1_source_archive import encode, MAX_SOURCE_RETURN_CHARS


def candidate_config(candidate='source-read'):
    if candidate == 'source-read':
        return SourceReadP1Agent, SYSTEM, READ_LIMIT, CONTINUATION_LIMIT
    if candidate == 'source-links-v1':
        from p1_linked_agent import LinkedSourceP1Agent, SYSTEM as linked_system
        from p1_linked_agent import READ_LIMIT as reads, CONTINUATION_LIMIT as continuations
        return LinkedSourceP1Agent, linked_system, reads, continuations
    if candidate == 'dms-inspired-v1':
        from p1_dms_agent import DMSP1Agent, SYSTEM as dms_system
        return DMSP1Agent, dms_system, 4, 2
    raise ValueError('unknown P1 candidate')


def source_identity(root=ROOT, *, strict=True, candidate='source-read'):
    from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run_certification import GAP_SOURCE_FILES, VENDOR_FILES
    from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.prepare_six_task_manifest import _committed_source_sha
    paths = list(GAP_SOURCE_FILES) + list(VENDOR_FILES) + [REL+'/'+name for name in (
        'p1_source_archive.py', 'p1_source_agent.py',
        'vendor/pma_89e5c0d/src/memory_agent/memory_enabled_agent.py',
        'vendor/pma_89e5c0d/external/harbor/src/harbor/llms/base.py',
        'vendor/pma_89e5c0d/external/harbor/src/harbor/llms/lite_llm.py',
        'vendor/pma_89e5c0d/external/harbor/src/harbor/llms/utils.py',
        'vendor/pma_89e5c0d/external/harbor/src/harbor/models/metric/usage_info.py')]
    candidate_config(candidate)
    if candidate in ('source-links-v1','dms-inspired-v1'):
        paths += [REL+'/p1_source_links.py', REL+'/p1_linked_agent.py']
    if candidate == 'dms-inspired-v1':
        paths += [REL+'/p1_dms_agent.py']
    paths += ['pma_evidence_review/tools/run_p1_source_case.py']
    return {'kind':'committed_sources' if strict else 'working_tree_sources',
            'code_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'source_files': {p:(_committed_source_sha(root,p) if strict else
                hashlib.sha256((root/p).read_bytes()).hexdigest()) for p in dict.fromkeys(paths)}}


def profile_client(profile, logs_dir):
    """Reuse the actual frozen profile wrapper; no actor/episode is started."""
    from episode import construct_upstream
    from citation_gate_config import BANK_DISPLAY_POLICY
    wrapper = construct_upstream(logs_dir, research_candidate='pma_gap_memory_v0',
        memory_maintenance_policy=BANK_DISPLAY_POLICY, memory_profile=profile)
    client=wrapper._memory_llm
    client.p1_parameters={k:profile.get(k,'unknown') for k in
        ('provider','api_mode','model','temperature','reasoning_effort','max_tokens','read_timeout','thinking_type')}
    client.p1_parameters['model']=client._model_name
    return client


def build_case(case, output, llm, *, candidate='source-read'):
    if case.get('schema') != 'p1-maintenance-case-v1':
        raise ValueError('unsupported frozen P1 case')
    bank = BankDisplayAgent.load_bank(deepcopy(case['initial_bank']))
    agent_type, _, _, _ = candidate_config(candidate)
    agent = agent_type(task=case['task'],task_id=case['task_id'],memory=bank,
        llm=llm,source_root=Path(output)/'source_archive')
    # These are explicitly reconstructed fixture inputs, not historical manifests.
    for window in case.get('source_windows',[]):
        agent.source_archive.capture(window['window_id'],window['model_input'],window['visible_events'])
    active = agent._active_records()
    for ref in case.get('entry_sources',[]):
        row = active[ref['memory_id']]
        if candidate in ('source-links-v1','dms-inspired-v1'):
            # Reconstructed old windows are broad legacy context, never exact event links.
            state = deepcopy(agent.links.state)
            agent.links.bind_state(state,row.id,row.category,row.content,
                {'sources':[], 'inherited_unassociated':[], 'association':'legacy_unassociated'}, ref['window_id'])
            agent.links.commit(state)
        else:
            agent.source_archive.bind(row.id,row.category,row.content,ref['window_id'])
    prior = case.get('prior_presentations',[])
    if candidate in ('source-links-v1','dms-inspired-v1'):
        agent.links.mark_presented(agent.links.ingest(prior))
    else:
        agent.source_archive.mark_presented(agent.source_archive.classify(prior))
    return agent


def write_json(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def public_parameters(llm):
    supplied=getattr(llm,'p1_parameters',{})
    attrs={'model':'_model_name','temperature':'_temperature','reasoning_effort':'_reasoning_effort'}
    return {k:supplied.get(k,getattr(llm,attrs.get(k,''),'unknown')) for k in
        ('provider','api_mode','model','temperature','reasoning_effort','max_tokens','read_timeout','thinking_type')}


async def run_case(case, output, llm, *, runtime_identity=None, candidate='source-read'):
    output=Path(output)
    stage='run_config'
    try:
        _, _, reads, continuations = candidate_config(candidate)
        runtime=runtime_identity if runtime_identity is not None else source_identity(strict=False, candidate=candidate)
        config={'continuation_protocol':'text_original_input_plus_visible_calls_and_receipts',
            'candidate':candidate,'native_messages_tool_roundtrip':False,'read_limit':reads,
            'continuation_limit':continuations,'serialized_source_result_char_limit':MAX_SOURCE_RETURN_CHARS,
            'p2_enabled':False,'task_enabled':False,'model_parameters':public_parameters(llm),
            'runtime':runtime,'canonical_case_data_sha256':hashlib.sha256(encode(case).encode()).hexdigest(),
            'physical_provider_request_count':'unknown; inherited client retry behavior', 'requests':[]}
        write_json(output/'run_config.json',config)
        stage='build_case'
        agent=build_case(case,output,llm,candidate=candidate)
        def before_request(request):
            config['requests'].append({'window_id':request['window_id'],
                'prompt_sha256':hashlib.sha256(request['prompt'].encode()).hexdigest(),
                'system_sha256':hashlib.sha256(request['system'].encode()).hexdigest(),
                'tool_schema_sha256':hashlib.sha256(encode(request['tools']).encode()).hexdigest()})
            write_json(output/'run_config.json',config)
        agent.before_request=before_request
        stage='maintenance'
        result=await agent.maintain(case['entries'],observation=case.get('observation'),
            step_count=case['step_count'],cycle_id='maintenance_1')
        write_json(output/'result.json',result)
        write_json(output/'bank_after.json',agent.memory.to_dict())
        write_json(output/'terminal.json',{'status':result['status'],'stage':'finished',
            'model_calls_attempted':result['model_calls_attempted'],
            'model_calls_completed':result['model_calls_completed']})
        return result
    except Exception as exc:
        terminal={'status':'engineering_error','stage':stage,'error_type':type(exc).__name__,
                  'model_calls_attempted':getattr(locals().get('agent'),'last_p1_report',{}).get('model_calls_attempted',0)}
        write_json(output/'terminal.json',terminal)
        return {**terminal,'operations':[],'reads_used':0,'continuations_used':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',required=True,type=Path,help='exactly one frozen case JSON')
    parser.add_argument('--output',required=True,type=Path,help='new private output directory')
    parser.add_argument('--candidate',choices=('source-read','source-links-v1','dms-inspired-v1'),default='source-read')
    parser.add_argument('--mode',choices=('scripted','real'),default='scripted')
    parser.add_argument('--profile-file',type=Path,help='existing private profile; real mode only')
    parser.add_argument('--authorize-real-p1',action='store_true',help='requires separate human authorization; never implied by this delivery')
    args=parser.parse_args()
    if args.mode=='real' and (not args.authorize_real_p1 or args.profile_file is None):
        parser.error('real P1 needs explicit authorization switch and an existing private profile')
    if args.output.exists():
        raise FileExistsError('do not retry an allocated case output')
    raw=args.case.read_bytes()
    case=json.loads(raw)
    identity=source_identity(candidate=args.candidate)
    _, actual_system, _, _ = candidate_config(args.candidate)
    args.output.mkdir(parents=True)
    run_identity={'mode':args.mode,'case_sha256':hashlib.sha256(raw).hexdigest(),
                  'runtime':identity,'candidate':args.candidate,'p1_system_sha256':hashlib.sha256(actual_system.encode()).hexdigest(),
                  'real_model_calls_requested':args.mode=='real'}
    (args.output/'identity.json').write_text(json.dumps(run_identity,indent=2)+'\n',encoding='utf-8')
    stage='client_initialization'
    try:
        if args.mode=='real':
            profile=json.loads(args.profile_file.read_text(encoding='utf-8'))['claude_monitor_opus48']
            llm=profile_client(profile,args.output/'client')
        else:
            async def noop(**kwargs):
                return NS(content='',tool_calls=[])
            llm=NS(call=noop)
        stage='case_runner'
        result=asyncio.run(run_case(case,args.output,llm,runtime_identity=identity,candidate=args.candidate))
    except Exception as exc:
        write_json(args.output/'terminal.json',{'status':'engineering_error','stage':stage,
            'error_type':type(exc).__name__,'model_calls_attempted':0})
        result={'status':'engineering_error','operations':[],'reads_used':0,'continuations_used':0}
    print(json.dumps({'status':result['status'],'mode':args.mode,'operations':len(result['operations']),
                      'reads_used':result['reads_used'],'continuations_used':result['continuations_used']}))
    return 0 if result['status']=='completed' else 1


if __name__=='__main__':
    raise SystemExit(main())
