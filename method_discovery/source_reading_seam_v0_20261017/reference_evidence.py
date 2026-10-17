"""Read the fixed public archive as data. Never execute its scripts or imports."""
import hashlib
import json
import re

ARCHIVE = '/workspace/scratch/ae13762e0e4d/current_evidence/CONSEQUENCE_THREE_CASE_PUBLIC_EVIDENCE.txt'
ARCHIVE_SHA256 = '8a9ba2f80fe62e233d06a096693996266763b61df4450dcf6e5c70665d20528c'
CONTEXT_MARKER = '\n\n## Context (Task Description + Recent Trajectory)\n'
PHASE1_TAIL = ('\n\n## Your Task\nAnalyze the trajectory and update the memory bank. '
               'Save important facts, record experiences, delete outdated entries. '
               "Be selective — only save what would be lost as the agent's context scrolls.\n")
UNITS = ('unit_01_07_candidate', 'unit_03_14_candidate', 'unit_05_18_candidate')


def read_archive(path=ARCHIVE):
    raw = open(path, 'rb').read()
    if hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('fixed public archive hash mismatch')
    archive = json.loads(raw)
    if archive['format'] != 'consequence-three-case-public-evidence-v1' or archive['file_count'] != 42:
        raise ValueError('unexpected archive identity')
    files = {}
    for item in archive['files']:
        data = item['utf8_text'].encode('utf-8')
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('archive entry hash/size mismatch: ' + item['path'])
        if item['path'] in files:
            raise ValueError('duplicate archive path')
        files[item['path']] = item['utf8_text']
    if len(files) != 42:
        raise ValueError('archive count mismatch')
    return files, hashlib.sha256(raw).hexdigest()


def load_cases(FrozenInputs, path=ARCHIVE):
    files, archive_hash = read_archive(path)
    cases = []
    for unit in UNITS:
        base = 'raw/' + unit + '/'
        requests = [json.loads(line) for line in files[base+'requests.jsonl'].splitlines()]
        p1 = next(row for row in requests if row['phase'] == 'phase1')
        prompt = p1['prompt']
        if not prompt.endswith(PHASE1_TAIL) or prompt.count(CONTEXT_MARKER) != 1:
            raise ValueError('captured prompt boundary changed')
        observation = prompt.split(CONTEXT_MARKER, 1)[1][:-len(PHASE1_TAIL)]
        if not observation.startswith('[Task Description]\n'):
            raise ValueError('no original task block')
        start = len('[Task Description]\n')
        match = re.search(r'\n\n\n\[Recent Trajectory \(last \d+ steps\)\]', observation)
        if match is None:
            raise ValueError('no original trajectory boundary')
        task = observation[start:match.start()]
        step = int(re.match(r'## Step (\d+)\n', prompt).group(1))
        # No authenticated update stream is supplied by this archive. We do not
        # infer updates from working memory, Task narrative, or bank prose.
        inputs = FrozenInputs.capture(task, (), observation,
                                      json.loads(files[base+'bank_before.json']), step)
        cases.append(dict(unit=unit, inputs=inputs, source=base+'requests.jsonl',
                          task_span=[start, match.start()], requests=requests))
    return cases, archive_hash
