"""Model-selected inquiry restored within the existing monitor session."""

import json
import time
import uuid


INQUIRY_PROMPT = """When a decision needs investigation, inquiry can keep your own question beside
selected original passages across wakes. Choose what evidence could distinguish the interpretations that
would lead you to act differently; a passing test matters only for the behavior it actually distinguishes.
Use the existing tools to investigate and revise your understanding, including your own advice. This is an
optional working view, not a checklist or a prerequisite for acting. It restores only passages you select,
not a complete or authoritative task model. Close or replace it when it no longer helps the decision;
unrelated root requirements remain in scope. No separate reviewer or automatic verdict is involved."""


class Inquiry:
    def __init__(self, workspace, atomic_write):
        self.workspace = workspace
        self.write = atomic_write

    def state(self):
        path = self.workspace.private_root / 'inquiry.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def archive(self, value):
        path = 'audit/inquiry/' + uuid.uuid4().hex + '.json'
        self.write(path, json.dumps(value, ensure_ascii=False))
        return 'monitor/' + path

    def call(self, action, question=None, sources=None):
        if action not in {'open', 'close'}:
            raise ValueError('action must be open or close')
        if action == 'close':
            if question is not None or sources is not None:
                raise ValueError('question and sources apply to open only')
            previous = self.state()
            if previous:
                self.archive(previous)
            self.write('inquiry.json', json.dumps({'active': False}))
            return {'status': 'closed', 'note': 'Only the selected view ended; no task input or approval.'}
        if not isinstance(question, str) or not question.strip():
            raise ValueError('Supply your current question in natural language')
        if not isinstance(sources, list) or not 1 <= len(sources) <= 8:
            raise ValueError('Select 1 to 8 source ranges; ordinary tools remain unrestricted')
        selected = []
        for source in sources:
            path = source['path']
            start, count = source.get('start', 1), source.get('count', 80)
            if type(start) is not int or type(count) is not int or start < 1 or not 1 <= count <= 1000:
                raise ValueError('Source range needs start >= 1 and count between 1 and 1000')
            self.workspace.resolve_read(path)  # Validate paths before replacing the selection.
            selected.append({'path': path, 'start': start, 'count': count})
        previous = self.state()
        if previous:
            self.archive(previous)
        state = {'active': True, 'question': question, 'sources': selected, 'selected_at': time.time()}
        self.write('inquiry.json', json.dumps(state, ensure_ascii=False))
        return self.restore()

    def restore(self):
        state = self.state()
        if not state or not state.get('active'):
            return None
        observations = []
        # Bounded restoration is a view, not a new evidence archive or a read restriction.
        for source in state['sources']:
            try:
                data = self.workspace.read_text(**{
                    'virtual_path': source['path'], 'start': source['start'], 'count': source['count']})
                content = data['content']
                data.update(content=content[:3000], truncated=len(content) > 3000,
                            observed_at=time.time())
                observations.append(data)
            except (OSError, ValueError) as exc:
                observations.append(dict(source, error=str(exc), observed_at=time.time()))
        result = {'question': state['question'][:6000],
                  'question_truncated': len(state['question']) > 6000,
                  'selection_file': 'monitor/inquiry.json', 'sources': observations,
                  'note': 'Your selected inquiry, restored from current source text. Line ranges may shift; '
                          'check relevance yourself. Truncated/missing passages are not negative evidence. '
                          'Use ordinary tools for more context; new findings continue in this same history.'}
        result['archive'] = self.archive(result)
        return result
