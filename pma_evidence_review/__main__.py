"""python -m pma_evidence_review --help"""
import argparse
import asyncio
import json
import re
from pathlib import Path

from .inputs import build, validate
from .location import locate
from .review import extraction_request, parse_claims, verification_requests, review
from .transport import CapturedTransport, FakeClient, load_profile_client


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build', help='Build one public development cycle; local files only')
    b.add_argument('--repo', default='.')
    b.add_argument('--sample', choices=['sqlite', 'html'], required=True)
    b.add_argument('--step', type=int)
    b.add_argument('--cycle-id')
    b.add_argument('--allow-redacted', action='store_true')
    b.add_argument('--out', required=True)
    for command in ('validate', 'export', 'fake', 'run-profile'):
        p = sub.add_parser(command)
        p.add_argument('--input', required=True)
        if command != 'validate':
            p.add_argument('--out', required=True)
            p.add_argument('--mode', choices=['evidence-first', 'batch'], default='evidence-first')
        if command == 'export':
            p.add_argument('--extraction-response', help='Optional saved JSON extraction response')
        if command == 'fake':
            p.add_argument('--responses', required=True, help='JSON array of raw response strings')
        if command == 'run-profile':
            p.add_argument('--repo', default='.')
            p.add_argument('--profile', required=True)
            p.add_argument('--profile-key', default='claude_monitor_opus48')
            p.add_argument('--execute-authorized-real-model', action='store_true')
    args = parser.parse_args()
    if args.command == 'build':
        write(args.out, build(args.repo, args.sample, step=args.step, cycle_id=args.cycle_id,
                             allow_redacted=args.allow_redacted))
        return
    packet = validate(read(args.input))
    if args.command == 'validate':
        print(json.dumps({'status': 'valid', 'replay_status': packet['replay_status'],
                          'limitations': packet['limitations']}))
        return
    if args.command == 'export':
        requests = [extraction_request(packet)]
        if args.extraction_response:
            claims, metadata, _, _ = parse_claims(Path(args.extraction_response).read_text(), packet)
            requests += [r for _, r in verification_requests(packet, claims, metadata, args.mode)]
        write(args.out, requests)
        return
    if args.command == 'run-profile' and not args.execute_authorized_real_model:
        parser.error('No request sent. Real execution requires separate user authorization and flag.')
    out = Path(args.out)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    client = FakeClient(read(args.responses)) if args.command == 'fake' else load_profile_client(
        args.repo, args.profile, args.profile_key, out / 'private_client', authorized=True)
    transport = CapturedTransport(client, out, fake=args.command == 'fake')
    result = asyncio.run(review(packet, transport, mode=args.mode, locator=locate))
    result['calls'] = {'client_calls': transport.calls, 'fake': transport.fake,
        'network_calls': 0 if transport.fake else 'not_measured_by_client_boundary',
        'provider_retries': 0 if transport.fake else 'see_native_provider_capture'}
    write(out / 'report.json', result)
    print(json.dumps({'client_calls': transport.calls, 'report': str(out / 'report.json')}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not expose client exception text, config content or credentials.
        code = str(error) if isinstance(error, ValueError) and re.fullmatch(
            r'[a-z0-9_]+', str(error)) else type(error).__name__
        raise SystemExit('Review failed (%s); inspect validated input and private captures.' % code)
