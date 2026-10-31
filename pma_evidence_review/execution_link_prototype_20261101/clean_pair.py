"""Manually frozen development references; not independent blind labels."""
from copy import deepcopy
from hashlib import sha256
import json

FACT = ('In the shown shell script, after exporting /app/sqlite/bin into PATH, lookup '
        'found /app/sqlite/bin/sqlite3; the captured stdout also contained a SQLite version line.')
PLAN = 'Next, verify availability from an independent process without relying on that export.'
REFERENCE = {'fact_only':'supported', 'fact_plus_plan':'supported'}


def pair_from_historical_B(material):
    """Use old call2's exact narrow sentence; change only future-plan appendage."""
    rows = []
    for name, content, claims in (
            ('fact_only', FACT, [FACT]),
            ('fact_plus_plan', FACT + ' ' + PLAN, [FACT, PLAN])):
        target = deepcopy(material)
        target['original_operation'] = {'op_index':0,'action':'save_knowledge','content':content}
        rows.append({'material':target,'claims':claims,'operation_kind':'save'})
    assert rows[0]['material']['submitted_evidence'] == rows[1]['material']['submitted_evidence']
    return rows


def evidence_identity(material):
    raw = json.dumps(material['submitted_evidence'],ensure_ascii=False,sort_keys=True,
                     separators=(',',':')).encode('utf-8')
    return sha256(raw).hexdigest()
