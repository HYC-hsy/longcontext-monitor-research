"""Separate submitted-citation CLI; never falls back to whole or whole-focus."""
import argparse
import asyncio
import json
import re
from pathlib import Path

from . import citation_inputs as inputs, citation_review as reviewer
from .__main__ import read, write
from .transport import CapturedTransport, FakeClient, load_profile_client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    build=sub.add_parser('build')
    build.add_argument('--repo',default='.')
    build.add_argument('--sample',choices=['sqlite','html'],required=True)
    build.add_argument('--out',required=True)
    for command in ('validate','export','fake','run-profile'):
        p=sub.add_parser(command)
        p.add_argument('--input',required=True)
        if command!='validate': p.add_argument('--out',required=True)
        if command=='fake': p.add_argument('--responses',required=True)
        if command=='run-profile':
            p.add_argument('--repo',default='.')
            p.add_argument('--profile',required=True)
            p.add_argument('--profile-key',default='claude_monitor_opus48')
            p.add_argument('--execute-authorized-real-model',action='store_true')
    args=parser.parse_args()
    if args.command=='build':
        write(args.out,inputs.build(args.repo,args.sample));return
    packet=inputs.validate(read(args.input))
    if args.command=='validate':
        print(json.dumps({'citation_input_sha256':packet['citation_input_sha256'],
            'parent_input_sha256':packet['parent_input_sha256'],'preparation':[
                {'op_index':r['operation']['op_index'],**{k:r['preparation'][k] for k in ('status','issues')}}
                for r in packet['operations']]}));return
    plans=reviewer.requests(packet)
    if args.command=='export': write(args.out,plans);return
    if args.command=='run-profile' and not args.execute_authorized_real_model:
        parser.error('No request sent. Real execution requires separate authorization and flag.')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False,mode=0o700)
    if args.command=='fake': client=FakeClient(read(args.responses))
    elif any(p['request'] for p in plans):
        client=load_profile_client(args.repo,args.profile,args.profile_key,out/'private_client',authorized=True)
    else: client=FakeClient([])
    transport=CapturedTransport(client,out,fake=args.command=='fake')
    report=asyncio.run(reviewer.review(packet,transport))
    write(out/'report.json',report)
    print(json.dumps({'report':str(out/'report.json')}))


if __name__=='__main__':
    try: main()
    except Exception as error:
        code=str(error) if isinstance(error,ValueError) and re.fullmatch(r'[a-z0-9_]+',str(error)) else type(error).__name__
        raise SystemExit('Citation review failed ('+code+'); inspect private validated inputs/captures.')
