"""No-model container probe using GA's actual code_run implementation.

The extraction CSV is an explicitly synthetic probe fixture. The source PDF
is a real financial task asset embedded in the pinned image; this probe never
claims to be a snapshot of a live Task's extraction.
"""

import hashlib
import json
from pathlib import Path

from ga import code_run


SCRIPT = r'''
from pathlib import Path
import csv, re, zlib
source = Path('/app/documents/UsN9tVTKskms.pdf')
binary = source.read_bytes()
streams = re.findall(rb'stream\r?\n(.*?)\r?\nendstream', binary, re.S)
if len(streams) != 1:
    raise RuntimeError('unexpected PDF content stream count')
decoded = zlib.decompress(streams[0]).decode('latin1')
match = re.search(r'\(TotalPrice\) Tj.*?\(([0-9]+(?:\.[0-9]+)?)\) Tj', decoded, re.S)
if not match:
    raise RuntimeError('source total not readable')
with Path('/app/extraction.csv').open(newline='', encoding='utf-8') as stream:
    row = next(csv.DictReader(stream))
if row['source'] != source.name:
    raise RuntimeError('extraction row does not identify source')
print('SOURCE_TOTAL=' + match.group(1))
print('OUTPUT_TOTAL=' + row['amount'])
print('SOURCE_MATCH=' + str(float(match.group(1)) == float(row['amount'])))
'''


def main():
    source = Path('/app/documents/UsN9tVTKskms.pdf')
    output = Path('/app/extraction.csv')
    gen = code_run(SCRIPT, 'python', timeout=30, cwd='/app', code_cwd='/app',
                   myprint=lambda *_args, **_kwargs: None)
    try:
        while True:
            next(gen)
    except StopIteration as done:
        result = done.value
    text = result.get('stdout', '')
    if result.get('exit_code') != 0 or 'SOURCE_MATCH=True' not in text:
        raise RuntimeError('real GA code_run failed to match source and output')
    print(json.dumps({
        'tool': 'GA code_run', 'status': 'passed',
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'source_total': '896.0', 'output_total': '896.0',
    }, sort_keys=True))


if __name__ == '__main__':
    main()
