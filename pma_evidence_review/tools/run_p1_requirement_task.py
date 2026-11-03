"""Empty-bank multi-cycle P1 scenario; no Task/P2. Scripted by default."""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from pma_evidence_review.tools.run_p1_source_case import (
    STAGE, REL, BankDisplayAgent, source_identity as base_identity, profile_client,
    write_json, public_parameters)
from p1_requirement_agent import RequirementP1Agent, SYSTEM
from p1_requirements import INIT_SYSTEM, INIT_TOOL, KEY
from p1_source_archive import encode, digest


def source_identity(*, strict=True):
    identity = base_identity(strict=strict,candidate='source-links-context-v1')
    paths = [REL+'/p1_requirements.py',REL+'/p1_requirement_agent.py',
             'pma_evidence_review/tools/run_p1_requirement_task.py']
    if strict:
        from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.prepare_six_task_manifest import _committed_source_sha
    for path in paths:
        identity['source_files'][path] = (_committed_source_sha(ROOT,path) if strict else
            hashlib.sha256((ROOT/path).read_bytes()).hexdigest())
    return identity


def validate_scenario(case):
    if (not isinstance(case,dict) or case.get('schema')!='p1-requirement-task-v1' or
            set(case)-{'schema','task','task_id','cycles'} or
            not isinstance(case.get('task'),str) or not case['task'].strip() or
            not isinstance(case.get('task_id'),str) or not case['task_id'] or
            not isinstance(case.get('cycles'),list) or not case['cycles']):
        raise ValueError('new task scenario required; no initial_bank or legacy migration')
    seen = set()
    for row in case['cycles']:
        if (not isinstance(row,dict) or set(row)-{'cycle_id','entries','observation','step_count'} or
                not isinstance(row.get('cycle_id'),str) or row['cycle_id'] in seen or
                not isinstance(row.get('entries'),list) or
                not all(isinstance(x,dict) for x in row['entries']) or
                ('observation' in row and not isinstance(row['observation'],str)) or
                not isinstance(row.get('step_count',0),int)):
            raise ValueError('invalid or duplicate cycle')
        seen.add(row['cycle_id'])


def build_task(case, output, llm, *, resume=False):
    validate_scenario(case)
    archive = Path(output)/'source_archive'
    if resume:
        payload = json.loads((archive/'source_links.json').read_bytes())
        state = payload['data']
        if payload['sha256']!=digest(encode(state)) or KEY not in state:
            raise ValueError('invalid candidate bundle')
        bank = BankDisplayAgent.load_bank(deepcopy(state['bank']))
    else:
        if archive.exists():
            raise FileExistsError('use a new private output or explicit --resume')
        from gap_store import GapMemory
        bank = GapMemory()
    return RequirementP1Agent(task=case['task'],task_id=case['task_id'],memory=bank,
                              llm=llm,source_root=archive)


async def run_task(case, output, llm, *, resume=False, identity=None):
    output = Path(output)
    agent = build_task(case,output,llm,resume=resume)
    config_path = output/'run_config.json'
    runtime = identity or source_identity(strict=False)
    config = {'candidate':'requirement-attributes-v1','scenario_sha256':digest(encode(case)),
        'runtime':runtime,'p1_only':True,'task_enabled':False,'p2_enabled':False,
        'model_parameters':public_parameters(llm),'requests':[],
        'budget':{'initialization':1,'maintenance_logical_calls':3,'total_reads':4,
                  'serial_read_turns':2,'last_turn':'write_only',
                  'physical_provider_requests':'unknown; inherited retries'}}
    if resume:
        previous = json.loads(config_path.read_bytes())
        if previous['scenario_sha256']!=config['scenario_sha256'] or previous['runtime']!=runtime:
            raise ValueError('resume requires identical scenario and runtime identity')
        config = previous
    def before(request):
        config['requests'].append({'kind':request['kind'],'cycle_id':request['cycle_id'],
            'window_id':request['window_id'],'prompt_sha256':digest(request['prompt']),
            'system_sha256':digest(request['system']),'tools_sha256':digest(encode(request['tools']))})
        write_json(config_path,config)
    write_json(config_path,config)
    agent.before_request = before
    results = []
    for cycle in case['cycles']:
        result = await agent.maintain(**deepcopy(cycle))
        results.append(result)
        write_json(output/'results.json',results)
        write_json(output/'bank_after.json',agent.memory.to_dict())
        write_json(output/'requirement_view.json',agent.export_view())
        if result['status']!='completed':
            break
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--mode',choices=('scripted','real'),default='scripted')
    parser.add_argument('--script',type=Path,help='JSON array of visible fake responses; scripted mode only')
    parser.add_argument('--profile-file',type=Path)
    parser.add_argument('--authorize-real-p1',action='store_true')
    args = parser.parse_args()
    if args.mode=='real' and (not args.authorize_real_p1 or not args.profile_file or args.script):
        parser.error('real mode requires explicit run authorization and private profile, no --script')
    if args.mode=='scripted' and (not args.script or args.profile_file or args.authorize_real_p1):
        parser.error('scripted mode requires --script, no profile or real authorization')
    stage, output_ready = 'output_initialization', False
    counts = {'model_calls_attempted':0,'model_calls_completed':0}
    try:
        if not args.resume:
            args.output.mkdir(parents=True,exist_ok=False)
        elif not args.output.is_dir():
            raise FileNotFoundError('resume needs the original private output directory')
        output_ready = True
        resume = args.resume
        if resume and not (args.output/'source_archive').exists():
            stage = 'resume_preflight'
            prior = json.loads((args.output/'terminal.json').read_bytes())
            safe_stages = {'scenario_loading','runtime_identity','script_loading','client_initialization'}
            if (prior.get('status')!='engineering_error' or prior.get('stage') not in safe_stages or
                    prior.get('model_calls_attempted')!=0 or prior.get('model_calls_completed')!=0 or
                    (args.output/'run_config.json').exists()):
                raise ValueError('no safe unstarted-run checkpoint')
            resume = False
        stage = 'scenario_loading'
        case = json.loads(args.scenario.read_bytes())
        validate_scenario(case)
        stage = 'runtime_identity'
        identity = source_identity()
        if args.mode=='real':
            stage = 'client_initialization'
            profile = json.loads(args.profile_file.read_bytes())['claude_monitor_opus48']
            client = profile_client(profile,args.output/'client')
        else:
            stage = 'script_loading'
            rows = json.loads(args.script.read_bytes())
            if not isinstance(rows,list):
                raise ValueError('script must be an array')
            for row in rows:
                if (not isinstance(row,dict) or set(row)-{'content','tool_calls'} or
                        not isinstance(row.get('content',''),str) or not isinstance(row.get('tool_calls',[]),list)):
                    raise ValueError('invalid scripted response')
                for call in row.get('tool_calls',[]):
                    if (not isinstance(call,dict) or set(call)!={'name','arguments'} or
                            not isinstance(call['name'],str) or not isinstance(call['arguments'],dict)):
                        raise ValueError('invalid scripted tool call')
            script = iter(rows)
            async def fake(**kwargs):
                row = next(script)
                return NS(content=row.get('content',''),tool_calls=[NS(function=NS(name=c['name'],
                    arguments=json.dumps(c['arguments'],ensure_ascii=False))) for c in row.get('tool_calls',[])])
            client = NS(call=fake)
        async def counted(**kwargs):
            counts['model_calls_attempted'] += 1
            response = await client.call(**kwargs)
            counts['model_calls_completed'] += 1
            return response
        llm = NS(call=counted,p1_parameters=public_parameters(client))
        stage = 'task_runner'
        result = asyncio.run(run_task(case,args.output,llm,resume=resume,identity=identity))
        terminal = {'status':result[-1]['status'],'stage':'finished','cycles_returned':len(result),
            'new_logical_calls':counts['model_calls_attempted'],'mode':args.mode,
            'task_enabled':False,'p2_enabled':False,**counts}
    except Exception as exc:
        terminal = {'status':'engineering_error','stage':stage,'error_type':type(exc).__name__,
            'mode':args.mode,'task_enabled':False,'p2_enabled':False,**counts}
    if output_ready:
        write_json(args.output/'terminal.json',terminal)
    print(json.dumps(terminal))
    return 0 if terminal['status']=='completed' else 1


if __name__=='__main__':
    raise SystemExit(main())
