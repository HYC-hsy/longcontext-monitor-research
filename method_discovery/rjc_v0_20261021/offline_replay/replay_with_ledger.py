"""Replay the production FailureLedger over the three archived SQLite runs.

Zero model calls. Reads only pos host events (tool_started/tool_outcome) that are
already committed in this repository. Prints a JSON report to stdout.
"""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]
from failure_ledger import FailureLedger  # noqa: E402

ROOT = HERE.parents[1]
ARCHIVES = {
    'pos-68764e0592a8481e': ROOT / ('pos_pma_shared_view_v1_20261020/raw_live_sqlite_contract_v2/'
                                    'pos/events.host.jsonl.part001.jsonl'),
    'pos-41c50cafd3b24b87': ROOT / ('pos_pma_shared_view_v1_20261020/raw_live_sqlite_httpdiag_v2_split/'
                                    'pos/events.host.jsonl.part001.jsonl'),
    'pos-bcb35740d2314ef1': ROOT / ('pos_upstream_ga_v1_20261017/raw_final_two_v2/03/'
                                    'pos_host/events.host.jsonl.part001.jsonl'),
}
SQLITE_TASK = ('Compile SQLite in /app/sqlite with gcov instrumentation and make it '
               'available in the PATH.\nThe SQLite source snapshot is pre-vendored at '
               '/app/vendor/sqlite-fossil-release.tar.gz; use it instead of fetching '
               'sources over the network.\n')


def replay(path, goal):
    ledger = FailureLedger(goal)
    turns = {}
    for line in path.open(encoding='utf-8'):
        row = json.loads(line)
        payload = row.get('payload', {})
        turn = payload.get('turn')
        if row.get('kind') == 'tool_started':
            turns.setdefault(turn, {'actions': [], 'sources': []})['actions'].append(
                {'id': payload['id'], 'name': payload['name'], 'order': payload.get('order', 0),
                 'arguments': payload.get('arguments') or {}, 'status': 'executed'})
        elif row.get('kind') == 'tool_outcome':
            turns.setdefault(turn, {'actions': [], 'sources': []})['sources'].append(
                {'origin': 'GA_tool_outcome', 'tool_use_id': payload['tool_use_id'],
                 'status': payload.get('status'), 'result': payload.get('result')})
    for turn in sorted(turns):
        ledger.ingest(turn=turn, transition_id=f'actor-transition-{turn}',
                      action_batch=turns[turn]['actions'], source_events=turns[turn]['sources'])
    return ledger


def main():
    report = {}
    for name, path in ARCHIVES.items():
        ledger = replay(path, SQLITE_TASK)
        report[name] = {
            'records': len(ledger.records),
            'goal_relevant_records': [r['failure_id'] for r in ledger.records if r['goal_relevant']],
            'open_at_end': [r['failure_id'] for r in ledger.open_records(goal_relevant_only=False)],
            'open_goal_relevant_at_end': [r['failure_id'] for r in ledger.open_records()],
            'panel_section_chars': len(ledger.panel_section()),
            'ledger': ledger.snapshot(),
        }
    json.dump(report, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
