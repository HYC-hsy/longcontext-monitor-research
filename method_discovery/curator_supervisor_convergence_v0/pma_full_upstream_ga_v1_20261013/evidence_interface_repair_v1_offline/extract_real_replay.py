"""Extract public development evidence only; never load hidden evaluator data."""
import ast
import gzip
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ARCHIVE = 'experiment_runner/evidence_gap_two_real_visible_20261025'
BASE_COMMIT = '016984a9f6f24d0fb1d330fd17feb8b3dd14c926'
RUNS = [('sqlite', 'pma-e8b1699a9e2b4a43', '/workspace/shared/sqlite_audit'),
        ('html', 'pma-ee5cd9d22ff34012', '/tmp/html-audit')]
HEADER = re.compile(r'^\[(s\w+) (\w+) event_order=(\d+) field=([^\]]+)\]\n'
                    r'(.*?)(?=\n\[s\w+ |\n## Your Task|\Z)', re.M | re.S)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def arguments(call):
    node = ast.parse(call, mode='eval')
    return json.loads(next(ast.literal_eval(k.value) for n in ast.walk(node)
                          if isinstance(n, ast.Call) for k in n.keywords
                          if k.arg == 'arguments'))


def extract():
    sources, cases, archives = {}, [], {}
    for label, run, local in RUNS:
        loaded = {}
        for name in ('pma_memory_payload.jsonl', 'pma_gap_visible_transport.jsonl'):
            path = f'{ARCHIVE}/{run}/{name}.gz'
            blob = (REPO / path).read_bytes()
            public = gzip.decompress(blob)
            # Optional audit copies must be byte-identical, not quietly substituted.
            audit = Path(local) / name
            if audit.exists():
                assert public == audit.read_bytes(), audit
            archives[path] = digest(blob)
            loaded[name] = [(i + 1, json.loads(line))
                            for i, line in enumerate(public.splitlines())]
        prompts = {row['value']['cycle_step']: (line, row)
                   for line, row in loaded['pma_memory_payload.jsonl']
                   if row['value']['phase'] == 'maintenance'}
        for tline, tr in loaded['pma_gap_visible_transport.jsonl']:
            t = tr['value']
            if t['phase'] != 'maintenance':
                continue
            step = t['cycle_step']
            pline, pr = prompts[step]
            spans = {m[1]: m for m in HEADER.finditer(pr['value']['prompt'])}
            for op, call in enumerate(t['tool_calls'] or []):
                for ei, ev in enumerate(arguments(call).get('evidence', [])):
                    m = spans[ev['source']]
                    raw, quote = m[5].rstrip('\n'), ev['quote']
                    if raw.count(quote) == 1:
                        continue
                    key = label + ':' + ev['source']
                    source = dict(raw=raw, raw_sha256=digest(raw.encode()), role=m[2],
                                  order=int(m[3]), field_path=m[4], old_handle=m[1])
                    if key in sources:
                        assert sources[key] == source
                    sources[key] = source
                    # Explicit developer-authored provenance mapping. Not a runtime
                    # resolver or a prediction that a model will select this child.
                    child = 'args/content' if label == 'html' else (
                            'args/script' if m[2] == 'tool_command' else 'stdout')
                    kind = 'decoded_unique'
                    if (label, step, op) in [('sqlite', 4, 0), ('sqlite', 9, 0)] and quote not in json.loads(raw).get('stdout', ''):
                        kind = 'noncontiguous'
                    if (label, step, op) == ('sqlite', 15, 1):
                        kind = 'wrong_source'
                    if raw.count(quote) > 1:
                        kind = 'ambiguous'
                    witness = None
                    if kind == 'wrong_source':
                        for other in spans.values():
                            try:
                                other_body = json.loads(other[5].rstrip('\n')).get('stdout', '')
                            except (ValueError, AttributeError):
                                continue
                            if quote in other_body:
                                witness = dict(old_handle=other[1], field_path=other[4]+'/stdout',
                                               raw=other[5].rstrip('\n'),
                                               raw_sha256=digest(other[5].rstrip('\n').encode()))
                                break
                        assert witness is not None
                    cases.append(dict(case_id=f'{label}-C{step}-op{op}-ref{ei}',
                        source_key=key, quote=quote, wrong_source_witness=witness, child_path=m[4]+'/'+child,
                        expected=kind, prompt_archive=f'{ARCHIVE}/{run}/pma_memory_payload.jsonl.gz',
                        prompt_line=pline, prompt_source_line=pr['source_line'],
                        prompt_source_line_sha256=pr['source_line_sha256'],
                        transport_archive=f'{ARCHIVE}/{run}/pma_gap_visible_transport.jsonl.gz',
                        transport_line=tline, transport_source_line=tr['source_line'],
                        transport_source_line_sha256=tr['source_line_sha256'],
                        operation_index=op, evidence_index=ei))
    return dict(base_commit=BASE_COMMIT, scope='public development data, no holdout',
                archives_sha256=archives, sources=sources, cases=cases)


if __name__ == '__main__':
    data = extract()
    (HERE / 'real_public_fixture.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(len(data['cases']), 'references;', len(data['sources']), 'deduplicated sources')
