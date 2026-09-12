"""Request-local file activity, not a semantic monitor or an event reviewer."""

import time


class LiveAwareness:
    PATHS = ('task/synopsis.jsonl', 'task/public_events.jsonl',
             'monitor/delivery_feedback.jsonl')

    def __init__(self, workspace):
        self.workspace = workspace
        self.previous = None
        self.sampled_at = None

    def context(self):
        now = time.time()
        stamps, descriptions = {}, []
        for name in self.PATHS:
            try:
                stat = self.workspace.resolve_read(name).stat()
                stamp = (stat.st_size, stat.st_mtime_ns)
                state = 'present'
                if self.previous is not None:
                    state = 'changed' if self.previous.get(name) != stamp else 'unchanged'
                descriptions.append(f'{name}: {state}, {stat.st_size} bytes')
            except FileNotFoundError:
                stamp = None
                descriptions.append(f'{name}: not present at sampling time')
            except (OSError, ValueError) as exc:
                stamp = ('unavailable', type(exc).__name__)
                descriptions.append(f'{name}: unavailable ({type(exc).__name__})')
            stamps[name] = stamp
        elapsed = (f'{max(0, now - self.sampled_at):.1f} seconds since the previous sample'
                   if self.sampled_at is not None else 'first sample in this Monitor process')
        self.previous, self.sampled_at = stamps, now
        # The raw values are audit metadata, never interpreted as uptake or risk.
        audit = {'sampled_at': now, 'stamps': stamps}
        text = (
            'Live file activity at request preparation (' + elapsed + '). '
            'This is metadata, not new evidence content or a judgment of what you have read. '
            'Changed does not mean wrong; unchanged does not mean understood or complete. '
            'The Task Agent can advance while you reason. Decide whether newer evidence could '
            'change your next action; use your existing tools when useful.\n'
            + '\n'.join(descriptions)
        )
        return text, audit
