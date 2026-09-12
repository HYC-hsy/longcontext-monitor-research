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

    @staticmethod
    def _preview(text, limit):
        text = str(text)
        return text if len(text) <= limit else text[:limit] + '\n[Preview clipped; read the original source for the rest.]'

    def _receipt(self):
        try:
            return json.loads(self.workspace.resolve_read(self.receipt_path).read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {}

    def attention(self):
        """Sample the existing first observation layer, never mark it read or judged."""
        try:
            path = self.workspace.resolve_read('task/synopsis.jsonl')
            with path.open('rb') as stream:
                stream.seek(0, 2)
                start = max(0, stream.tell() - 65536)
                stream.seek(start)
                lines = stream.read().splitlines()
            if start:
                lines = lines[1:]  # May start in the middle of a record.
            recent = []
            for line in reversed(lines):
                try:
                    record = json.loads(line)
                    if isinstance(record, dict):
                        recent.append(record)
                except ValueError:
                    continue  # Concurrent partial append is not evidence.
                if len(recent) == 4:
                    break
            recent.reverse()
            snapshots = '\n'.join(self._preview(json.dumps(r, ensure_ascii=False), 1000) for r in recent)
        except FileNotFoundError:
            snapshots = 'No synopsis is available yet.'
        except (OSError, ValueError) as exc:
            snapshots = 'Synopsis unavailable: ' + type(exc).__name__
        try:
            receipt = self._receipt()
            guidance = self._preview(receipt.get('message', ''), 1500)
        except (OSError, ValueError) as exc:
            guidance = 'Last submitted input unavailable: ' + type(exc).__name__
        return ('Current first-layer synopsis, sampled just before this request; not proof, not a read cursor. '
                'The task may advance during inference. Earlier evidence remains available through tools.\n'
                + snapshots + '\nLast submitted correction (not proof of delivery or uptake):\n' + guidance)

    @staticmethod
    def _passages(text, source):
        # Original line-addressable excerpts, not a generated semantic layer.
        passages, chunk, start = [], [], 1
        for line_no, line in enumerate(text.splitlines(), 1):
            if chunk and sum(map(len, chunk)) + len(line) > 1400:
                passages.append((f'{source}#L{start}-L{line_no - 1}', '\n'.join(chunk)))
                chunk, start = [], line_no
            chunk.append(line)
        if chunk:
            passages.append((f'{source}#L{start}-L{len(text.splitlines())}', '\n'.join(chunk)))
        return passages

    def _rank(self, passages, query, budget):
        indices = BM25Index([text for _, text in passages]).search(query, top_k=5) if passages and query.strip() else []
        result, remaining = [], budget
        for i in indices:
            source, text = passages[i]
            if remaining <= 0:
                break
            excerpt = self._preview(text, min(1400, remaining))
            result.append({'source': source, 'text': excerpt})
            remaining -= len(excerpt)
        return result

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
            if relative.as_posix() == 'working.md' or any(part.startswith('.') or part == 'audit' for part in relative.parts):
                continue
            virtual = 'monitor/' + relative.as_posix()
            resolved = self.workspace.resolve_read(virtual)
            passages.extend(self._passages(resolved.read_text(encoding='utf-8', errors='replace'), virtual))
        return self._rank(passages, query, 2000)

    def read(self, query='', after_correction=True, steps=8):
        if not isinstance(query, str) or type(after_correction) is not bool:
            raise ValueError('query must be text and after_correction boolean')
        if type(steps) is not int or not 1 <= steps <= 32:
            raise ValueError('steps must be between 1 and 32')
        task = self.workspace.resolve_read('task/original_task.txt').read_text(encoding='utf-8')
        try:
            working = self.workspace.resolve_read('monitor/working.md').read_text(encoding='utf-8')
        except FileNotFoundError:
            working = ''
        receipt = self._receipt()
        after = int(receipt.get('cursor_at_submission', 0)) if after_correction else 0
        rows, malformed = self._events(steps, after)
        field_budget = max(60, 7500 // (max(1, len(rows)) * 3))
        trajectory = [RefinerTrajectoryStep(
            step_index=int(event.get('archive_sequence') or line),
            thought=self._preview(event.get('response_content') or '', field_budget),
            action=self._preview(json.dumps(event.get('tool_calls') or [], ensure_ascii=False), field_budget),
            observation=self._preview(json.dumps(event.get('tool_results') or [], ensure_ascii=False), field_budget),
        ) for line, event in rows]
        rendered = TrajectoryFormatter.format_trajectory(trajectory)
        # GA actions are JSON tool calls, not bash; no upstream renderer rewrite.
        rendered = rendered.replace('```bash\n', '```json\n')
        notes = self._notes(query)
        task_matches = self._rank(self._passages(task, 'task/original_task.txt'), query, 4500)
        task_view = (json.dumps(task_matches, ensure_ascii=False) if task_matches else self._preview(task, 4500))
        state = 'Your revisable working note (not verified truth):\n' + self._preview(working, 2000)
        if notes:
            state += '\nQuery-matched private passages:\n' + json.dumps(notes, ensure_ascii=False)
        builder = PromptBuilder({'user_template': (
            'Original task:\n{{ISSUE_DESCRIPTION}}\n'
            '<state_summary>{{STATE_SUMMARY}}</state_summary>\n'
            '<latest_guidance>{{LATEST_GUIDANCE}}</latest_guidance>\n'
            'Recent public evidence:\n{{RECENT_TRAJECTORY}}')})
        _, context = builder.build_prompt(task_view, rendered, state, self._preview(receipt.get('message', ''), 1500))
        return {
            'context': context,
            'query': query, 'after_submission_cursor': after,
            'sources': [f'task/public_events.jsonl#L{line}' for line, _ in rows],
            'last_cursor': int(rows[-1][1].get('archive_sequence') or rows[-1][0]) if rows else after,
            'malformed_records_skipped': malformed,
            'limits': (
                f'Latest at most {steps} public event records, not necessarily complete Agent turns. '
                'Earlier events remain in the original archive; missing evidence is not absence. '
                'Task excerpts and private note matches are lexical, not verified facts or exhaustive coverage. '
                'Actions, observations and notes are explicitly clipped previews, not complete evidence. Read original '
                'files/tests with file_read or code_run as needed. Submission does not prove uptake.'),
        }
