"""Replay R1 inputs through new view formatting; no model or task execution."""
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'GenericAgent-main'))
from monitor_agent_core.decision_context import DecisionContext
from monitor_agent_core.workspace import MonitorWorkspace

AGENT = ROOT / 'long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-literature-transfer-20260913-r1/fyn-2.2.0-roadmap__moZMPPE/agent'
dialogue = [json.loads(line) for line in (AGENT / 'monitor/monitor_private/audit/dialogue.jsonl').read_text(encoding='utf-8').splitlines()]
events = (AGENT / 'monitor/task_evidence/public_events.jsonl').read_text(encoding='utf-8').splitlines()
report = []
with tempfile.TemporaryDirectory(prefix='monitor-r2-view-') as temporary:
    root = Path(temporary)
    evidence = root / 'evidence'
    evidence.mkdir()
    (evidence / 'original_task.txt').write_text((AGENT / 'monitor/task_evidence/original_task.txt').read_text(encoding='utf-8'), encoding='utf-8')
    workspace = MonitorWorkspace(evidence, root / 'private')
    view = DecisionContext(workspace)
    for call in dialogue:
        if call['event'] != 'tool_call' or call['name'] != 'review_context':
            continue
        old = next(r['data'] for r in dialogue if r['event'] == 'tool_result' and r['tool_id'] == call['tool_id'])
        note = re.search(r'<state_summary>(.*?)</state_summary>', old['context'], re.S).group(1)
        note = note.split('Query-matched private passages:')[0].removeprefix('Your revisable working note (not verified truth):\n')
        workspace.write_text('monitor/working.md', note)
        (evidence / 'public_events.jsonl').write_text('\n'.join(events[:old['last_cursor']]) + '\n', encoding='utf-8')
        guidance = re.search(r'<latest_guidance>(.*?)</latest_guidance>', old['context'], re.S).group(1)
        workspace.write_text(view.receipt_path, json.dumps({'cursor_at_submission': 0, 'message': guidance}))
        args = json.loads(call['arguments'])
        # Same window isolates formatting; does not test new follow-up default.
        new = view.read(**args, after_correction=False)
        assert old['sources'] == new['sources']
        assert len(new['context']) < 22000
        report.append({'tool_id': call['tool_id'], 'old_characters': len(old['context']),
                       'new_characters': len(new['context']), 'same_event_sources': True,
                       'task_source_links': 'task/original_task.txt#L' in new['context']})
destination = Path(__file__).with_name('r2_view_comparison.json')
destination.write_text(json.dumps({'limits': 'Shape-only replay; notes reconstructed from archived views; no behavioral or cost-effectiveness proof.', 'comparisons': report}, indent=2) + '\n')
print(json.dumps(report, indent=2))
