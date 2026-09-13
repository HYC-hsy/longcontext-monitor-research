"""File-based observation entry; no semantic retrieval or review tool."""
import json
from collections import deque
from datetime import datetime, timezone


class DecisionContext:
    # Existing candidate configuration name, not the retired tool API.
    def __init__(self, workspace, bank_owned=False):
        self.workspace = workspace
        self.bank_owned = bank_owned
        self.receipt_path = 'monitor/audit/decision_context_last_input.json'

    def _receipt(self):
        try:
            return json.loads(self.workspace.resolve_read(self.receipt_path).read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {}

    def _recent(self, name, count):
        rows = deque(maxlen=count)
        try:
            path = self.workspace.resolve_read('task/' + name)
            with path.open(encoding='utf-8') as stream:
                for line_no, line in enumerate(stream, 1):
                    if not line.endswith('\n'):
                        continue
                    try:
                        value = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(value, dict):
                        rows.append((line_no, value))
        except FileNotFoundError:
            pass
        return list(rows)

    def record_input(self, message):
        rows = self._recent('public_events.jsonl', 1)
        cursor = int(rows[-1][1].get('archive_sequence') or rows[-1][0]) if rows else 0
        self.workspace.write_text(self.receipt_path, json.dumps({
            'cursor_at_submission': cursor, 'message': message,
        }, ensure_ascii=False))

    def attention(self):
        """Refresh navigation; return its location, not another evidence packet."""
        try:
            rows = self._recent('synopsis.jsonl', 4)
            receipt = self._receipt()
            text = ('# Observation overview\n\n'
                    'Generated navigation, not a correctness judgment or a record of what you inspected.\n'
                    'Updated UTC: ' + datetime.now(timezone.utc).isoformat() + '\n\n'
                    '## Your ongoing understanding\n'
                    'Read and maintain monitor/working.md with ordinary file tools. '
                    'It is your revisable understanding, not evidence. This generated file does not replace it. '
                    'Edit working.md, not this automatically refreshed navigation file.\n\n'
                    '## Original materials\n'
                    '- Full task: task/original_task.txt\n'
                    '- Full chronological navigation: task/synopsis.jsonl\n'
                    '- Full public actions and results: task/public_events.jsonl\n'
                    '- Private decision/tool history: monitor/audit/dialogue.jsonl\n'
                    '- Intervention delivery: monitor/delivery_feedback.jsonl\n'
                    'Live code, tests and other mounted sources:\n')
            text += ''.join(f'- task/{name}/: {path}\n' for name, path in self.workspace.task_mounts.items())
            if (self.workspace.private_root / 'task_model.md').exists():
                text += '\nTask interpretation: monitor/task_model.md (original task remains authoritative).\n'
            text += ('\n## Last submitted correction\n'
                     + json.dumps(receipt, ensure_ascii=False, indent=2)
                     + '\nSubmission is not proof of uptake. Earlier reactions remain in the full chronology.\n'
                     '\n## Latest synopsis records\n'
                     'Only the latest four records, not all changes since you last looked. '
                     'These are navigation, not implementation or test evidence. '
                     'No per-field truncation is applied here.\n')
            for line, record in rows:
                text += f'\nSource: task/synopsis.jsonl line {line}\n'
                text += json.dumps(record, ensure_ascii=False, indent=2) + '\n'
            if not rows:
                text += '\nNo complete synopsis record available yet.\n'
            if self.bank_owned:
                text = text.replace('Read and maintain monitor/working.md with ordinary file tools.',
                                    'Current memory: monitor/pma_memory.json; update it with memory operations.')
                text = text.replace('Edit working.md, not this automatically refreshed navigation file.',
                                    'This automatically refreshed file is navigation, not a second memory.')
            self.workspace.write_text('monitor/overview.md', text)
            notice = ('Observation entry refreshed: monitor/overview.md. Your continuing understanding is '
                    'in monitor/working.md and this conversation. Use ordinary file/code tools to regain '
                    'your bearings and inspect original materials as needed; the entry is navigation, not proof.')
            return notice.replace('monitor/working.md', 'the memory bank') if self.bank_owned else notice
        except (OSError, ValueError) as exc:
            return ('Observation entry refresh failed: ' + type(exc).__name__ +
                    '. Any existing overview may be stale. Original task/, monitor/working.md and history remain available.')
