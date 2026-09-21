"""Separate model-authored task interpretation from changing local progress."""
import re


class TaskUnderstanding:
    def __init__(self, workspace):
        self.workspace = workspace
        self.path = workspace.private_root / 'task_model.md'
        self.draft = None

    def read(self):
        return self.path.read_text(encoding='utf-8') if self.path.exists() else ''

    def context(self):
        text = self.draft or self.read()
        return ('Task interpretation, subordinate to the full original task at task/original_task.txt. '
                'This is not a progress report or certified evidence. Revise an interpretation only from '
                'the task or better evidence, not because a local correction has finished.\n' +
                (text or 'No task interpretation has been established yet.'))

    def initialization_instruction(self):
        return ('\nIn this existing maintenance response, also write a natural-language task interpretation '
                'inside <task_model>...</task_model> in your response text, alongside any bank tool calls. '
                'Understand the required behaviors, constraints and what observations could distinguish '
                'fulfillment from a merely present artifact. Cover the original task, not just the first '
                'subtask. No fixed fields, invented requirements, implementation prescription or completion '
                'scoreboard. This is revisable interpretation; the original task remains authoritative.')

    def capture(self, text):
        matches = re.findall(r'<task_model>(.*?)</task_model>', text or '', re.S)
        if len(matches) != 1 or not matches[0].strip():
            raise RuntimeError('Initial maintenance omitted one nonempty task_model text block')
        self.draft = ('# Task understanding\n\n'
                      'Original task (full, authoritative): task/original_task.txt\n\n' + matches[0].strip())

    def commit(self):
        if self.draft is not None:
            self.workspace.write_text('monitor/task_model.md', self.draft)
            self.draft = None

    def completion_context(self):
        original = self.workspace.resolve_read('task/original_task.txt').read_text(encoding='utf-8')
        return ('\nDecision scope changed to a task handoff. First interpret whether this is completion, '
                'a question or a blocker. For completion, assess the original whole task, not only whether '
                'your corrections were followed. Local repair promises do not authorize root completion. '
                'Choose checks for material unresolved grounds; not every unknown requires investigation.\n'
                '## Full original task\n' + original + '\n## Current interpretation\n' + self.context())
