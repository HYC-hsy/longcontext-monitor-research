"""Explicit prompt-only A/B plans over the unchanged, validated frozen dataset."""
import argparse
import asyncio
import copy
import json
from pathlib import Path

from . import core
from .. import citation_review as cr
from ..transport import CapturedTransport, FakeClient, load_profile_client

from ..prompt_strategy import (BASELINE, CANDIDATE, ONE_SENTENCE, BASELINE_CODE,
                               CLARIFICATION, SUPPORT_SENTENCE, apply_strategy)


def plan(dataset, manifest_sha256, strategy=BASELINE):
    core.old.require(strategy in (BASELINE,CANDIDATE,ONE_SENTENCE), 'experiment_strategy')
    cases=core.load_dataset(dataset,manifest_sha256)['cases.json']
    entries=[]
    for case in cases:
        request=apply_strategy(case['request'],strategy)
        entries.append({'sample_id':case['sample_id'],
            'parent_benchmark_input_sha256':case['benchmark_input_sha256'],
            'parent_audit_request_sha256':case['request']['audit_request_sha256'],
            'request':request})
    result={'schema':'citation-prompt-experiment-v1','baseline_code_sha':BASELINE_CODE,
            'dataset_manifest_sha256':manifest_sha256,'strategy':strategy,'entries':entries}
    result['experiment_plan_sha256']=core.ci.identity(result)
    return result


async def run(dataset, manifest_sha256, transport, strategy=BASELINE, *, on_result=None):
    frozen=plan(dataset,manifest_sha256,strategy)
    base=core.load_dataset(dataset,manifest_sha256)['cases.json']
    entries={e['sample_id']:e for e in frozen['entries']}
    by_request={c['request']['audit_request_sha256']:(c['request'],entries[c['sample_id']]['request'])
                for c in base}
    core.old.require(len(by_request)==len(base), 'ambiguous_parent_request')

    class PlannedTransport:
        async def send(self, request):
            original,actual=by_request[request['audit_request_sha256']]
            core.old.require(request==original, 'unexpected_parent_request')
            return await transport.send(actual)

    results=[]
    def save(row):
        row=copy.deepcopy(row);entry=entries[row['sample_id']]
        row.update(experiment_strategy=strategy,experiment_plan_sha256=frozen['experiment_plan_sha256'],
                   parent_audit_request_sha256=entry['parent_audit_request_sha256'],
                   audit_request_sha256=entry['request']['audit_request_sha256'])
        results.append(row)
        if on_result is not None:on_result(row)
    await core.run(dataset,PlannedTransport(),expected_manifest_sha256=manifest_sha256,on_result=save)
    return results


def score(dataset, manifest_sha256, results, strategy=BASELINE):
    frozen=plan(dataset,manifest_sha256,strategy)
    entries={e['sample_id']:e for e in frozen['entries']}
    restored=[]
    for row in results:
        entry=entries.get(row.get('sample_id'))
        core.old.require(entry is not None, 'unknown_experiment_result')
        core.old.require(row.get('experiment_strategy')==strategy and
            row.get('experiment_plan_sha256')==frozen['experiment_plan_sha256'] and
            row.get('benchmark_input_sha256')==entry['parent_benchmark_input_sha256'] and
            row.get('parent_audit_request_sha256')==entry['parent_audit_request_sha256'] and
            row.get('audit_request_sha256')==entry['request']['audit_request_sha256'],
            'experiment_result_identity')
        # Only after verifying actual experimental identity, adapt for the unchanged scorer.
        copy_row=copy.deepcopy(row);copy_row['audit_request_sha256']=entry['parent_audit_request_sha256']
        restored.append(copy_row)
    docs=core.load_dataset(dataset,manifest_sha256,include_evaluation=True)
    report=core.score(docs['cases.json'],docs['evaluation-only.json'],restored)
    counts={}
    for cycle in docs['inventory.json']['cycles']:
        for row in cycle.get('operations',[]):
            status=row['preparation'];counts[status]=counts.get(status,0)+1
    report.update(experiment_strategy=strategy,experiment_plan_sha256=frozen['experiment_plan_sha256'],
                  historical_preparation_counts=counts,
                  eligible_not_in_main=len(docs['inventory.json']['eligible_not_in_main']))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['export','fake','run-profile','score'])
    parser.add_argument('--dataset',required=True)
    parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--strategy',choices=[BASELINE,CANDIDATE,ONE_SENTENCE],default=BASELINE)
    parser.add_argument('--out',required=True)
    parser.add_argument('--results')
    parser.add_argument('--repo',default='.')
    parser.add_argument('--profile')
    parser.add_argument('--profile-key',default='claude_monitor_opus48')
    parser.add_argument('--execute-authorized-real-model',action='store_true')
    args=parser.parse_args()
    if args.command=='run-profile' and (not args.execute_authorized_real_model or not args.profile):
        parser.error('No request sent. Existing profile, separate authorization and explicit flag required.')
    frozen=plan(args.dataset,args.manifest_sha256,args.strategy)
    if args.command=='export':core.write(args.out,frozen);return
    if args.command=='score':
        if not args.results:parser.error('--results required')
        results=core.ci.strict_json(Path(args.results).read_text(encoding='utf-8'))
        core.write(args.out,score(args.dataset,args.manifest_sha256,results,args.strategy));return
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    core.write(out/'experiment-plan.json',frozen)
    if args.command=='fake':
        responses=[json.dumps({'op_index':e['request']['op_index'],'verdict':'insufficient',
                    'explanation':'Offline transport fixture, not semantic judgment.'}) for e in frozen['entries']]
        client=FakeClient(responses)
    else:
        client=load_profile_client(args.repo,args.profile,args.profile_key,out/'private_client',authorized=True)
    transport=CapturedTransport(client,out,fake=args.command=='fake')
    with (out/'results.jsonl').open('x',encoding='utf-8',newline='\n') as journal:
        def save(row):journal.write(json.dumps(row,ensure_ascii=False)+'\n');journal.flush()
        results=asyncio.run(run(args.dataset,args.manifest_sha256,transport,args.strategy,on_result=save))
    core.write(out/'results.json',results)
    if any(r['engineering_status'] not in {'ok','not_run_after_engineering_error'} for r in results):
        raise SystemExit('Experiment stopped on engineering error; inspect saved results. No retry.')


if __name__=='__main__':main()
