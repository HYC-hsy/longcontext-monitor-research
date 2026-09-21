"""Opt-in, model-owned follow-up over original public bytes, not a verdict engine."""

import json
import time
import uuid


FOCUS_PROMPT = """For a concern worth following across actions, feedback_focus can keep a private
natural note beside the subsequent original public record and delivery receipts. Begin before intervening,
or supply after_event from the public archive to revisit an earlier point. Read when useful; it does not
wake you, send messages, classify progress, or require approval. Decide whether new behavior changes your
advice or makes further attention unnecessary. Closing this local view never closes the root task.
monitor/focus.md is freely editable with ordinary tools. The view is chronological, not topic-filtered;
unrelated developments may matter. General tools, broader history and original task remain available."""


class FeedbackFocus:
    def __init__(self, workspace, atomic_write):
        self.workspace = workspace
        self.atomic_write = atomic_write

    def _state(self):
        path = self.workspace.resolve_private('monitor/focus_cursor.json')
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def _save(self, state):
        self.atomic_write('focus_cursor.json', json.dumps(state))

    def _archive(self, state):
        note = self.workspace.resolve_private('monitor/focus.md')
        self.atomic_write('audit/focus/' + uuid.uuid4().hex + '.json', json.dumps({
            'state': state, 'note': note.read_text(encoding='utf-8') if note.exists() else '',
        }, ensure_ascii=False))

    def _event_offset(self, after_event):
        # Physical JSONL navigation only; never infer relevance or a repair match.
        path = self.workspace.evidence_root / 'public_events.jsonl'
        if not path.exists():
            if after_event not in (None, 0):
                raise ValueError('No public events exist at that cursor')
            return 0
        offset, count = 0, 0
        with path.open('rb') as stream:
            while after_event is None or count < after_event:
                line = stream.readline()
                if not line or not line.endswith(b'\n'):
                    break  # An in-flight record remains unread.
                count += 1
                offset = stream.tell()
        if after_event is not None and count != after_event:
            raise ValueError('after_event exceeds the complete public archive')
        return offset

    def _page(self, virtual, offset, limit):
        try:
            path = self.workspace.resolve_read(virtual)
        except FileNotFoundError:
            if offset:
                raise ValueError('Previously read source disappeared: ' + virtual)
            return {'source': virtual, 'text': '', 'next_byte': 0, 'more': False,
                    'available': False}
        size = path.stat().st_size
        if size < offset:
            raise ValueError('Source was truncated; reopen focus explicitly: ' + virtual)
        with path.open('rb') as stream:
            stream.seek(offset)
            data = stream.read(min(limit, size - offset))
        # Preserve UTF-8 boundaries even when a single event is larger than a page.
        while data:
            try:
                text = data.decode('utf-8')
                break
            except UnicodeDecodeError as exc:
                if exc.reason != 'unexpected end of data':
                    raise
                data = data[:exc.start]
        else:
            text = ''
        end = offset + len(data)
        return {'source': virtual, 'start_byte': offset, 'next_byte': end,
                'observed_size': size, 'more': end < size, 'text': text,
                'format': 'Original UTF-8 slice; JSON records may span pages. Read again for continuation.'}

    def call(self, action, note=None, after_event=None, limit=12000):
        if action not in {'begin', 'read', 'close'}:
            raise ValueError('action must be begin, read or close')
        if not 256 <= limit <= 64000:
            raise ValueError('limit must be between 256 and 64000 bytes per stream')
        state = self._state()
        if action == 'begin':
            if not isinstance(note, str) or not note.strip():
                raise ValueError('begin needs a natural note about what you are following')
            if after_event is not None and (not isinstance(after_event, int) or after_event < 0):
                raise ValueError('after_event must be a nonnegative public event cursor')
            offset = self._event_offset(after_event)
            if state:
                self._archive(state)
            state = {'active': True, 'started_at': time.time(), 'event_byte': offset,
                     'receipt_byte': 0, 'after_event': after_event}
            self.atomic_write('focus.md', note)
            self._save(state)
            return {'status': 'opened', 'note_path': 'monitor/focus.md',
                    'starts_at_byte': offset, 'note':
                    'Nothing sent or approved. read retrieves subsequent public bytes; receipts include all inputs.'}
        if note is not None or after_event is not None:
            raise ValueError('note/after_event apply to begin; edit monitor/focus.md to revise without resetting')
        if not state or not state['active']:
            return {'status': 'inactive', 'note': 'No local focus; ordinary observation tools remain available.'}
        if action == 'close':
            self._archive(state)
            state['active'] = False
            self._save(state)
            return {'status': 'closed', 'note': 'Local view closed, not root completion. No input sent.'}
        note_path = self.workspace.resolve_private('monitor/focus.md')
        note_text = note_path.read_text(encoding='utf-8') if note_path.exists() else ''
        events = self._page('task/public_events.jsonl', state['event_byte'], limit)
        receipts = self._page('monitor/delivery_feedback.jsonl', state['receipt_byte'], limit)
        result = {'status': 'read', 'observed_at': time.time(), 'note': note_text[:6000],
                  'note_truncated': len(note_text) > 6000, 'note_path': 'monitor/focus.md',
                  'public': events, 'delivery': receipts,
                  'boundary': 'A read is not understanding or resolution. Delivery is not uptake. '
                              'Evidence can change while you decide; broader task remains in scope.'}
        # Save the exact returned observation before advancing; available through ordinary tools.
        archive = 'audit/focus/' + uuid.uuid4().hex + '.json'
        self.atomic_write(archive, json.dumps(result, ensure_ascii=False))
        state.update(event_byte=events['next_byte'], receipt_byte=receipts['next_byte'])
        self._save(state)
        result['archive'] = 'monitor/' + archive
        return result
