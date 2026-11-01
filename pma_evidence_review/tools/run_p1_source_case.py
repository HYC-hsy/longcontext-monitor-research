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
from p1_source_agent import SourceReadP1Agent, SYSTEM
from p1_source_archive import encode


def source_identity(root=ROOT):
    from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run_certification import GAP_SOURCE_FILES, VENDOR_FILES
    from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.prepare_six_task_manifest import _committed_source_sha
    paths = list(GAP_SOURCE_FILES) + list(VENDOR_FILES) + [REL+'/'+name for name in (
        'p1_source_archive.py', 'p1_source_agent.py',
        'vendor/pma_89e5c0d/src/memory_agent/memory_enabled_agent.py',
        'vendor/pma_89e5c0d/external/harbor/src/harbor/llms/base.py',
        'vendor/pma_89e5c0d/external/harbor/src/harbor/llms/lite_llm.py',
        'vendor/pma_89e5c0d/external/harbor/src/harbor/llms/utils.py')]
    paths += ['pma_evidence_review/tools/run_p1_source_case.py']
    return {'code_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'source_files': {p:_committed_source_sha(root,p) for p in dict.fromkeys(paths)}}


def profile_client(profile, logs_dir):
    """Reuse the actual frozen profile wrapper; no actor/episode is started."""
    from episode import construct_upstream
    from citation_gate_config import BANK_DISPLAY_POLICY
    wrapper = construct_upstream(logs_dir, research_candidate='pma_gap_memory_v0',
        memory_maintenance_policy=BANK_DISPLAY_POLICY, memory_profile=profile)
    return wrapper._memory_llm


def build_case(case, output, llm):
    if case.get('schema') != 'p1-maintenance-case-v1':
        raise ValueError('unsupported frozen P1 case')
    bank = BankDisplayAgent.load_bank(deepcopy(case['initial_bank']))
    agent = SourceReadP1Agent(task=case['task'],task_id=case['task_id'],memory=bank,
        llm=llm,source_root=Path(output)/'source_archive')
    # These are explicitly reconstructed fixture inputs, not historical manifests.
    for window in case.get('source_windows',[]):
        agent.source_archive.capture(window['window_id'],window['model_input'],window['visible_events'])
    active = agent._active_records()
    for ref in case.get('entry_sources',[]):
        row = active[ref['memory_id']]
        agent.source_archive.bind(row.id,row.category,row.content,ref['window_id'])
    prior = case.get('prior_presentations',[])
    agent.source_archive.mark_presented(agent.source_archive.classify(prior))
    return agent


async def run_case(case, output, llm):
    agent = build_case(case,output,llm)
    result = await agent.maintain(case['entries'],observation=case.get('observation'),
        step_count=case['step_count'],cycle_id='maintenance_1')
    Path(output,'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    Path(output,'bank_after.json').write_text(json.dumps(agent.memory.to_dict(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',required=True,type=Path,help='exactly one frozen case JSON')
    parser.add_argument('--output',required=True,type=Path,help='new private output directory')
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
    identity=source_identity()
    args.output.mkdir(parents=True)
    run_identity={'mode':args.mode,'case_sha256':hashlib.sha256(raw).hexdigest(),
                  'runtime':identity,'p1_system_sha256':hashlib.sha256(SYSTEM.encode()).hexdigest(),
                  'real_model_calls_requested':args.mode=='real'}
    (args.output/'identity.json').write_text(json.dumps(run_identity,indent=2)+'\n',encoding='utf-8')
    if args.mode=='real':
        profile=json.loads(args.profile_file.read_text(encoding='utf-8'))['claude_monitor_opus48']
        llm=profile_client(profile,args.output/'client')
    else:
        async def noop(**kwargs):
            return NS(content='',tool_calls=[])
        llm=NS(call=noop)
    result=asyncio.run(run_case(case,args.output,llm))
    print(json.dumps({'status':result['status'],'mode':args.mode,'operations':len(result['operations']),
                      'reads_used':result['reads_used'],'continuations_used':result['continuations_used']}))
    return 0 if result['status']=='completed' else 1


if __name__=='__main__':
    raise SystemExit(main())
