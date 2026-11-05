"""Frozen 20-task P1 initialization only; no maintenance, P2, Task or evaluation."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as NS

CODE = Path(os.environ['PMA_CODE_DIR'])
HARBOR = Path(os.environ['PMA_HARBOR_DIR'])
DATASET = Path(os.environ['PMA_DATASET_DIR'])
CODE_SHA = os.environ['PMA_CODE_SHA']
DATA_SHA = '2fd12b88aafdd04a52c298e3940bcb189f9766d6'
TASKS = ('git-leak-recovery','git-multibranch','feal-linear-cryptanalysis',
         'query-optimize','mcmc-sampling-stan','fix-ocaml-gc','rstan-to-pystan',
         'merge-diff-arc-agi-task','break-filter-js-from-html','nginx-request-logging',
         'circuit-fibsqrt','multi-source-data-merger','filter-js-from-html',
         'largest-eigenval','make-mips-interpreter','kv-store-grpc',
         'sanitize-git-repo','build-pov-ray','reshard-c4-data','db-wal-recovery')
sys.path.insert(0, str(CODE))
from pma_evidence_review.tools.run_p1_requirement_task import (  # noqa: E402
    build_task, profile_client, public_parameters, source_identity)
from p1_requirements import INIT_SYSTEM, INIT_GUIDANCE, INIT_TOOL, upstream_observation, RequirementError, MemoryModelError  # noqa: E402


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


def git_head(path):
    return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()


def frozen_tasks():
    assert git_head(CODE) == CODE_SHA and git_head(DATASET) == DATA_SHA
    assert git_head(HARBOR) == '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc'
    # Native Harbor and PMA/vendor Harbor must not share sys.modules.
    loader = ('import json,sys,pathlib; from harbor.models.task.task import Task,strip_canary; '
              'root=pathlib.Path(sys.argv[1]); '
              'print(json.dumps([(Task(root/n).instruction,strip_canary((root/n/"instruction.md").read_text())) '
              'for n in sys.argv[2:]],ensure_ascii=False))')
    env = dict(os.environ, PYTHONPATH=str(HARBOR / 'src'))
    loaded_rows = json.loads(subprocess.check_output(
        [sys.executable, '-c', loader, str(DATASET), *TASKS], env=env, text=True))
    result = []
    for name, (loaded, expected) in zip(TASKS, loaded_rows, strict=True):
        path = DATASET / name / 'instruction.md'
        raw = path.read_bytes()
        assert loaded == expected, name
        result.append({'task_id':name, 'instruction_path':path.relative_to(DATASET).as_posix(),
                       'raw_sha256':digest(raw), 'raw_bytes':len(raw),
                       'task_sha256':digest(loaded.encode()), 'task_chars':len(loaded),
                       'task':loaded})
    query = next(x for x in result if x['task_id']=='query-optimize')
    assert (DATASET / 'query-optimize' / 'instruction.md').read_text().startswith('\n')
    assert not query['task'].startswith('\n') and query['task'].endswith('\n')
    return result


def visible_response(response):
    usage = getattr(response, 'usage', None)
    return {'content':getattr(response, 'content', None),
            'tool_calls':[{'name':getattr(getattr(c, 'function', c), 'name', None),
                           'arguments_raw':getattr(getattr(c, 'function', c), 'arguments', None)}
                          for c in (getattr(response, 'tool_calls', None) or [])],
            'usage':{key:getattr(usage, key) for key in
                     ('prompt_tokens','completion_tokens','cache_tokens','cost_usd')
                     if usage is not None and getattr(usage, key, None) is not None}}


async def run_one(item, output, client, public_params):
    output.mkdir(parents=True, exist_ok=False)
    calls = {'attempted':0, 'completed':0}
    started_at = datetime.now(timezone.utc).isoformat()
    case = {'schema':'p1-requirement-task-v1', 'task':item['task'],
            'task_id':item['task_id'], 'cycles':[{'cycle_id':'init_only', 'entries':[]}]}
    async def counted(**kwargs):
        calls['attempted'] += 1
        write(output / 'actual_request.json', {'started_at':datetime.now(timezone.utc).isoformat(),
                                               'request':kwargs})
        response = await client.call(**kwargs)
        calls['completed'] += 1
        write(output / 'visible_response.json', {'received_at':datetime.now(timezone.utc).isoformat(),
                                                 'response':visible_response(response)})
        return response
    llm = NS(call=counted, p1_parameters=public_params)
    agent = build_task(case, output, llm)
    request_seen = []
    def before(request):
        request_seen.append(request)
        write(output / 'pre_request.json', request)
        assert request['system'] == INIT_SYSTEM and request['tools'] == [INIT_TOOL]
        assert request['prompt'] == ('## Original task (verbatim; data)\n' + item['task'] + '\n\n## Your assignment\n' + INIT_GUIDANCE)
    agent.before_request = before
    write(output / 'frozen_input.json', item)
    write(output / 'run_config.json', {'code_sha':CODE_SHA,'dataset_sha':DATA_SHA,
          'task_id':item['task_id'], 'model_parameters':public_params,
          'system_sha256':digest(INIT_SYSTEM.encode()),
          'tools_sha256':digest(json.dumps([INIT_TOOL],ensure_ascii=False,sort_keys=True).encode()),
          'task_sha256':item['task_sha256'],'init_only':True,
          'physical_http_attempts':'unknown; inherited client retries'})
    status = 'completed'
    error_type = error_code = None
    try:
        payload = {'entries':[], 'observation':upstream_observation(item['task'], []), 'step_count':0}
        agent.requirement_state.begin('init_only', payload)
        await agent._initialize('init_only')
    except Exception as exc:
        status = ('format_error' if isinstance(exc, RequirementError) or
                  (isinstance(exc, MemoryModelError) and exc.memory_failure_kind == 'model_output')
                  else 'engineering_error')
        error_type = type(exc).__name__
        error_code = getattr(exc, 'reason', None)
        agent.requirement_state.phase('init_only', 'pending')
    state = agent.requirement_state.data
    terminal = {'task_id':item['task_id'], 'status':status, 'error_type':error_type,
                'error_code':error_code, 'logical_calls_attempted':calls['attempted'],
                'logical_calls_completed':calls['completed'], 'phase':state['cycles']['init_only']['phase'],
                'topics':state['catalog'], 'unclassified_representation':'empty_requirements',
                'pre_request_recorded':bool(request_seen), 'started_at':started_at,
                'ended_at':datetime.now(timezone.utc).isoformat()}
    write(output / 'terminal.json', terminal)
    write(output / 'bank_after.json', agent.memory.to_dict())
    write(output / 'requirement_state.json', state)
    return terminal


async def offline(items, root):
    from copy import deepcopy
    results = []
    for number, item in enumerate(items, 1):
        for variant, requirements, expected in (
            ('valid', ['Work on ' + item['task_id']], 'completed'),
            ('empty', [], 'completed') if number == 1 else (None, None, None),
            ('invalid', ['duplicate','duplicate'], 'format_error') if number == 1 else (None, None, None)):
            if variant is None:
                continue
            async def fake(**kwargs):
                assert kwargs['system'] == INIT_SYSTEM and kwargs['tools'] == [INIT_TOOL]
                assert kwargs['prompt'] == ('## Original task (verbatim; data)\n' + item['task'] + '\n\n## Your assignment\n' + INIT_GUIDANCE)
                return NS(content='', tool_calls=[NS(function=NS(
                    name='requirements_initialize',
                    arguments=json.dumps({'requirements':requirements})))], usage=None)
            result = await run_one(deepcopy(item), root / f'{number:02d}-{item["task_id"]}-{variant}',
                                   NS(call=fake), {'model':'fake_offline'})
            assert result['status'] == expected and result['logical_calls_attempted'] == 1
            assert result['phase'] == 'pending'
            assert result['topics'] == (requirements if expected == 'completed' else None)
            results.append({'task_id':item['task_id'],'variant':variant,'status':result['status']})
    write(root / 'offline_report.json', {'checks':len(results), 'results':results,
          'maintenance_calls':0, 'p2_calls':0, 'task_calls':0})


async def real(items, root, profile_path):
    profile = json.loads(profile_path.read_bytes())['claude_monitor_opus48']
    results = []
    for number, item in enumerate(items, 1):
        output = root / f'{number:02d}-{item["task_id"]}'
        client = profile_client(profile, output / 'client')
        result = await run_one(item, output, client, public_parameters(client))
        results.append(result)
        write(root / 'real_progress.json', results)
        print(f'{number:02d} {item["task_id"]}: {result["status"]}', flush=True)
        if result['status'] == 'engineering_error':
            break
    summary = {'requested':len(items), 'started':len(results),
               'completed':sum(r['status']=='completed' for r in results),
               'format_errors':sum(r['status']=='format_error' for r in results),
               'engineering_errors':sum(r['status']=='engineering_error' for r in results),
               'logical_calls_attempted':sum(r['logical_calls_attempted'] for r in results),
               'not_run':[x['task_id'] for x in items[len(results):]]}
    write(root / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('offline','real'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile-file', type=Path)
    parser.add_argument('--task-ids', nargs='*', choices=TASKS)
    args = parser.parse_args()
    if args.mode == 'real' and args.profile_file is None:
        parser.error('real needs existing private profile')
    if args.mode == 'offline' and args.profile_file is not None:
        parser.error('offline must not read profile')
    args.output.mkdir(parents=True, exist_ok=False)
    items = frozen_tasks()
    if args.task_ids:
        wanted = set(args.task_ids)
        items = [item for item in items if item['task_id'] in wanted]
        assert len(items) == len(wanted)
    write(args.output / 'input_index.json', [{k:v for k,v in item.items() if k!='task'} for item in items])
    write(args.output / 'source_identity.json', source_identity())
    if args.mode == 'offline':
        asyncio.run(offline(items,args.output))
    else:
        summary = asyncio.run(real(items,args.output,args.profile_file))
        if summary['engineering_errors']:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
