"""Query-conditioned view over original evidence and model-owned Markdown.

The upstream components rank and render; this module only adapts sources.
No model invocation, semantic event classification, or second memory writer.
"""
import json
from collections import deque

from .vendor.pma_bm25 import BM25Index
from .vendor.liveplan_types import RefinerTrajectoryStep
from .vendor.liveplan_formatters import TrajectoryFormatter, PromptBuilder


class DecisionContext:
    def __init__(self, workspace):
        self.workspace = workspace
        self.receipt_path = 'monitor/audit/decision_context_last_input.json'

    def _events(self, steps, after=0):
        selected, skipped = deque(maxlen=steps), 0
        try:
            path = self.workspace.resolve_read('task/public_events.jsonl')
        except FileNotFoundError:
            return [], 0
        with path.open(encoding='utf-8') as stream:
            for line_no, line in enumerate(stream, 1):
                try:
                    event = json.loads(line)
                except ValueError:
                    skipped += 1
                    continue
                if not isinstance(event, dict):
                    skipped += 1
                    continue
                if int(event.get('archive_sequence') or line_no) > after:
                    selected.append((line_no, event))
        return list(selected), skipped

    def record_input(self, message):
        events, _ = self._events(1)
        cursor = int(events[-1][1].get('archive_sequence') or events[-1][0]) if events else 0
        self.workspace.write_text(self.receipt_path, json.dumps({
            'cursor_at_submission': cursor, 'message': message,
        }, ensure_ascii=False))

    def _notes(self, query):
        passages = []
        root = self.workspace.private_root
        for path in sorted(root.rglob('*.md')):
            relative = path.relative_to(root)
            if any(part.startswith('.') or part == 'audit' for part in relative.parts):
                continue
            virtual = 'monitor/' + relative.as_posix()
            resolved = self.workspace.resolve_read(virtual)
            lines = resolved.read_text(encoding='utf-8', errors='replace').splitlines()
            for start in range(0, len(lines), 30):
                text = '\n'.join(lines[start:start + 30])
                if text.strip():
                    passages.append((f'{virtual}#L{start + 1}-L{min(start + 30, len(lines))}', text))
        if not passages or not query.strip():
            return []
        indices = BM25Index([text for _, text in passages]).search(query, top_k=5)
        return [{'source': passages[i][0], 'text': passages[i][1]} for i in indices]

    def read(self, query='', after_correction=False, steps=8):
        if not isinstance(query, str) or type(after_correction) is not bool:
            raise ValueError('query must be text and after_correction boolean')
        if type(steps) is not int or not 1 <= steps <= 32:
            raise ValueError('steps must be between 1 and 32')
        task = self.workspace.resolve_read('task/original_task.txt').read_text(encoding='utf-8')
        try:
            working = self.workspace.resolve_read('monitor/working.md').read_text(encoding='utf-8')
        except FileNotFoundError:
            working = ''
        try:
            receipt = json.loads(self.workspace.resolve_read(self.receipt_path).read_text(encoding='utf-8'))
        except FileNotFoundError:
            receipt = {}
        after = int(receipt.get('cursor_at_submission', 0)) if after_correction else 0
        rows, malformed = self._events(steps, after)
        trajectory = [RefinerTrajectoryStep(
            step_index=int(event.get('archive_sequence') or line),
            thought=str(event.get('response_content') or ''),
            action=json.dumps(event.get('tool_calls') or [], ensure_ascii=False),
            observation=json.dumps(event.get('tool_results') or [], ensure_ascii=False),
        ) for line, event in rows]
        rendered = TrajectoryFormatter.format_trajectory(trajectory)
        # GA actions are JSON tool calls, not bash; no upstream renderer rewrite.
        rendered = rendered.replace('```bash\n', '```json\n')
        notes = self._notes(query)
        state = 'Your revisable working note (not verified truth):\n' + working
        if notes:
            state += '\nQuery-matched private passages:\n' + json.dumps(notes, ensure_ascii=False)
        builder = PromptBuilder({'user_template': (
            'Original task:\n{{ISSUE_DESCRIPTION}}\n'
            '<state_summary>{{STATE_SUMMARY}}</state_summary>\n'
            '<latest_guidance>{{LATEST_GUIDANCE}}</latest_guidance>\n'
            'Recent public evidence:\n{{RECENT_TRAJECTORY}}')})
        _, context = builder.build_prompt(task, rendered, state, receipt.get('message'))
        return {
            'context': context,
            'query': query, 'after_submission_cursor': after,
            'sources': [f'task/public_events.jsonl#L{line}' for line, _ in rows],
            'last_cursor': int(rows[-1][1].get('archive_sequence') or rows[-1][0]) if rows else after,
            'malformed_records_skipped': malformed,
            'limits': (
                f'Latest at most {steps} public event records, not necessarily complete Agent turns. '
                'Earlier events remain in the original archive; missing evidence is not absence. '
                'Upstream renderer shortens observations beyond 5000 characters. Private note matches '
                'are lexical retrieval, not verified facts or exhaustive coverage. Read original '
                'files/tests with file_read or code_run as needed. Submission does not prove uptake.'),
        }
