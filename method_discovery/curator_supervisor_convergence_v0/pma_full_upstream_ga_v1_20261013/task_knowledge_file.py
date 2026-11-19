"""Task-readable knowledge projection on the existing per-task read-only mount."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

TASK_MEMORY_PATH = '/run/pma-bridge/responses/knowledge/memory.json'
TASK_MEMORY_NOTICE = (
    '\n\nAfter receiving this reminder, you must open the knowledge bank at ' + TASK_MEMORY_PATH +
    " and cross-check the reminder against the relevant entries before acting, so you don't miss "
    'important information and can recover any additional context needed for your judgment.')


class KnowledgePublicationError(BaseException):
    """Fatal: never turn a successful host write but failed projection into success."""


class TaskKnowledgeFile:
    def __init__(self, memory, response_dir: Path, *, run_id: str, task_id: str):
        self.memory = memory
        directory = Path(response_dir) / 'knowledge'
        if directory.exists() or directory.is_symlink():
            raise KnowledgePublicationError('task knowledge directory must start fresh')
        directory.mkdir()
        directory.chmod(0o755)
        self.path = directory / 'memory.json'
        self.run_id, self.task_id = run_id, task_id
        self.failed = False
        if self.path.exists() or self.path.is_symlink():
            raise KnowledgePublicationError('task knowledge file must start fresh')
        if memory.knowledge:
            raise KnowledgePublicationError('task knowledge must start empty')
        self.publish()
        original_save = memory.save_knowledge

        def save_and_publish(content):
            if self.failed:
                raise KnowledgePublicationError('task knowledge publication previously failed')
            memory_id = original_save(content)
            # Publish only after the original storage method accepted the content.
            # A failure stops the event before any success receipt can be returned.
            self.publish()
            return memory_id

        memory.save_knowledge = save_and_publish

    def publish(self):
        if self.failed:
            raise KnowledgePublicationError('task knowledge publication previously failed')
        pending = None
        try:
            payload = {'run_id': self.run_id, 'task_id': self.task_id,
                       'knowledge': [entry.to_dict() for entry in self.memory.knowledge]}
            encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
            # Do not rewrite or append duplicates when nothing changed.
            if self.path.is_symlink():
                raise ValueError('task knowledge path is a symlink')
            if self.path.exists() and self.path.read_bytes() == encoded:
                return
            fd, pending = tempfile.mkstemp(prefix='.memory-', dir=self.path.parent)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            # Host and Task may have different UIDs; the mount is Task-read-only.
            os.chmod(pending, 0o644)
            os.replace(pending, self.path)
        except Exception as exc:
            self.failed = True
            raise KnowledgePublicationError('task knowledge publication failed') from exc
        finally:
            if pending is not None and os.path.exists(pending):
                os.unlink(pending)

    def append_notice(self, reminder):
        self.publish()
        if isinstance(reminder, str) and reminder.strip():
            return reminder + TASK_MEMORY_NOTICE
        return reminder
