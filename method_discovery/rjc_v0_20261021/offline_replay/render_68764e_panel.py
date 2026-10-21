import sys, json, asyncio
from pathlib import Path
root = Path(sys.argv[1])
sys.path[:0] = [str(root/'method_discovery/rjc_v0_20261021'), str(root/'method_discovery/rjc_v0_20261021/offline_replay')]
from replay_with_ledger import replay, ARCHIVES, SQLITE_TASK
ledger = replay(ARCHIVES['pos-68764e0592a8481e'], SQLITE_TASK)
print('=== PANEL SECTION (pos-68764e, after final receipt) ===')
print(ledger.panel_section())
print()
gaps = [{'gap_type':'achievement','target':'SQLite installed in /app/sqlite','reason':'binaries built but not yet installed to target directory'},
        {'gap_type':'achievement','target':'SQLite binary available in PATH','reason':'task requires PATH availability'},
        {'gap_type':'epistemic','target':'current PATH environment variable configuration','reason':'need to determine how to make sqlite available in PATH'}]
rev = ledger.completion_review(open_gaps=gaps, stale=True, state_version=5)
print('=== COMPLETION REVIEW PROMPT (what the Task would see once) ===')
print(rev['prompt'])
print('chars:', len(rev['prompt']))
