"""Local-only dataset build, validation, export, fake wiring and reference scoring."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from . import core
from ..transport import CapturedTransport, FakeClient, load_profile_client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('build');p.add_argument('--repo',default='.');p.add_argument('--out',required=True)
    p.add_argument('--specs',default=str(Path(__file__).with_name('specs.json')))
    for cmd in ('validate','export','fake','score','run-profile'):
        p=sub.add_parser(cmd);p.add_argument('--dataset',required=True)
        p.add_argument('--manifest-sha256',required=True)
        if cmd!='validate':p.add_argument('--out',required=True)
        if cmd=='score':p.add_argument('--results',required=True)
        if cmd=='run-profile':
            p.add_argument('--repo',default='.')
            p.add_argument('--profile',required=True)
            p.add_argument('--profile-key',default='claude_monitor_opus48')
            p.add_argument('--execute-authorized-real-model',action='store_true')
    args=parser.parse_args()
    if args.command=='build':
        core.build(args.repo,json.loads(Path(args.specs).read_text(encoding='utf-8')),args.out);return
    if args.command=='run-profile' and not args.execute_authorized_real_model:
        parser.error('No request sent. Separate real-model authorization and explicit flag required.')
    documents=core.load_dataset(args.dataset,args.manifest_sha256,include_evaluation=args.command=='score')
    cases=documents['cases.json']
    if args.command=='validate':print(json.dumps({'cases':len(cases),'status':'valid'}));return
    if args.command=='export':
        core.write(args.out,[{'sample_id':c['sample_id'],**c['request']} for c in cases]);return
    if args.command=='score':
        labels=documents['evaluation-only.json']
        report=core.score(cases,labels,json.loads(Path(args.results).read_text(encoding='utf-8')))
        audit=documents['inventory.json'];counts={}
        for cycle in audit['cycles']:
            for row in cycle.get('operations',[]):
                status=row['preparation'];counts[status]=counts.get(status,0)+1
        report['historical_preparation_counts']=counts
        report['eligible_not_in_main']=len(audit['eligible_not_in_main'])
        core.write(args.out,report);return
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    if args.command=='fake':
        # Fixed fake response intentionally ignores reference labels.
        responses=[json.dumps({'op_index':c['request']['op_index'],'verdict':'insufficient',
                               'explanation':'Offline transport fixture, not semantic judgment.'}) for c in cases]
        client=FakeClient(responses)
    else:
        client=load_profile_client(args.repo,args.profile,args.profile_key,out/'private_client',authorized=True)
    transport=CapturedTransport(client,out,fake=args.command=='fake')
    # Flush each completed or skipped result before considering the next case.
    with (out/'results.jsonl').open('x',encoding='utf-8') as journal:
        def save_result(row):
            journal.write(json.dumps(row,ensure_ascii=False)+'\n');journal.flush()
        results=asyncio.run(core.run(args.dataset,transport,expected_manifest_sha256=args.manifest_sha256,
                                    on_result=save_result))
    core.write(out/'results.json',results)
    if any(r['engineering_status'] not in {'ok','not_run_after_engineering_error'} for r in results):
        raise SystemExit('Benchmark stopped on engineering error; inspect results.json and results.jsonl. No retry.')


if __name__=='__main__':main()
