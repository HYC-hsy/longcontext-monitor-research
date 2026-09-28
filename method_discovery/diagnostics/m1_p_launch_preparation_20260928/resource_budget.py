"""Experimental resource accounting, not epistemic state or a semantic gate.

No prices, providers, task execution or approval actions in this module.
The ledger is an audit/control resource file; never project it into prompts.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import time
import uuid


class BudgetStop(RuntimeError):
    pass


class ResourceBudget:
    def __init__(self, path, record, limits):
        self.path = Path(path)
        self.record = record
        self.limits = limits

    @contextmanager
    def transaction(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix('.lock').open('a+b') as lock:
            lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                if lock.read(1) == b'':
                    lock.write(b'0'); lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                data = json.loads(self.path.read_text()) if self.path.exists() else {
                    'records': {}, 'events': [], 'pending': {}, 'panel_calls': 0,
                    'panel_input': 0, 'panel_output': 0,
                    'panel_started': time.monotonic(),
                    'monetary_limit_enforced': False}
                yield data
                temp = self.path.with_suffix('.new')
                temp.write_text(json.dumps(data, indent=2), encoding='utf-8')
                os.replace(temp, self.path)
            finally:
                if os.name == 'nt':
                    lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def begin(self, role, purpose, review, input_reserve, output_reserve):
        # Reserve the entire permitted retry envelope before admitting a call.
        # These caller-supplied estimates are NOT provider-enforced upper bounds.
        attempt_limit = self.limits['attempts_per_call']
        if attempt_limit < 1 or input_reserve < 0 or output_reserve < 0:
            raise ValueError('invalid reservation')
        per_input, per_output = input_reserve, output_reserve
        input_reserve *= attempt_limit
        output_reserve *= attempt_limit
        rejected = None
        ident = uuid.uuid4().hex
        with self.transaction() as d:
            r = d['records'].setdefault(self.record, {
                'calls': {'task': 0, 'monitor': 0}, 'reviews': {}, 'attempts': 0,
                'review_starts': {},
                'input': 0, 'output': 0, 'cache_read': 0, 'cache_write': 0,
                'provider_seconds': {'task': 0.0, 'monitor': 0.0},
                'started': time.monotonic(), 'blocked': False})
            pending = [v for v in d['pending'].values() if v['record'] == self.record]
            review_count = r['reviews'].get(str(review), 0)
            if role == 'monitor':
                r['review_starts'].setdefault(str(review), time.monotonic())
            if d.get('panel_paused'):
                rejected = 'panel_resource_paused'
            elif r['blocked']:
                rejected = 'unknown_usage_or_previous_limit'
            elif r['calls'][role] >= self.limits[role + '_calls']:
                rejected = 'record_logical_call_limit'
            elif d['panel_calls'] >= self.limits['panel_calls']:
                rejected = 'panel_logical_call_limit'
            elif role == 'monitor' and purpose == 'review' and review_count >= self.limits['review_calls']:
                rejected = 'review_logical_call_limit'
            elif time.monotonic() - r['started'] >= self.limits['record_wall_seconds']:
                rejected = 'record_wall_limit'
            elif time.monotonic() - d['panel_started'] >= self.limits['panel_wall_seconds']:
                rejected = 'panel_wall_limit'
            elif role == 'monitor' and time.monotonic() - r['review_starts'][str(review)] >= self.limits['review_wall_seconds']:
                rejected = 'review_wall_limit'
            elif r['provider_seconds'][role] >= self.limits[role + '_provider_seconds']:
                rejected = 'provider_time_limit'
            elif r['input'] + sum(v['input_reserve'] for v in pending) + input_reserve > self.limits['record_input']:
                rejected = 'input_reservation_limit'
            elif r['output'] + sum(v['output_reserve'] for v in pending) + output_reserve > self.limits['record_output']:
                rejected = 'output_reservation_limit'
            elif d['panel_input'] + sum(v['input_reserve'] for v in d['pending'].values()) + input_reserve > self.limits['panel_input']:
                rejected = 'panel_input_reservation_limit'
            elif d['panel_output'] + sum(v['output_reserve'] for v in d['pending'].values()) + output_reserve > self.limits['panel_output']:
                rejected = 'panel_output_reservation_limit'
            if rejected:
                d['events'].append({'event': 'budget_request_denied', 'reason': rejected, 'record': self.record})
            else:
                r['calls'][role] += 1
                if role == 'monitor' and purpose == 'review':
                    r['reviews'][str(review)] = review_count + 1
                d['panel_calls'] += 1
                d['pending'][ident] = {'record': self.record, 'role': role,
                    'purpose': purpose, 'review': review, 'attempts': 0,
                    'input_reserve': input_reserve, 'output_reserve': output_reserve,
                    'per_attempt_input_reserve': per_input,
                    'per_attempt_output_reserve': per_output,
                    'attempt_limit': attempt_limit,
                    'started': time.monotonic(), 'usage_records': []}
                d['events'].append({'event': 'logical_call_started', 'id': ident,
                    'record': self.record, 'role': role, 'purpose': purpose, 'review': review})
        if rejected:
            raise BudgetStop(rejected)
        return ident

    def attempt(self, ident):
        rejected = None
        with self.transaction() as d:
            p = d['pending'][ident]
            if p['attempts'] > len(p['usage_records']):
                self._pause(d, ident, 'previous_attempt_usage_unknown')
            if d.get('panel_paused'):
                rejected = 'panel_resource_paused'
                d['events'].append({'event': 'provider_attempt_denied', 'id': ident, 'reason': rejected})
            elif p['attempts'] >= p['attempt_limit']:
                rejected = 'attempt_limit'
                d['events'].append({'event': 'attempt_limit_denied', 'id': ident})
            else:
                p['attempts'] += 1
                d['records'][self.record]['attempts'] += 1
                d['events'].append({'event': 'provider_attempt_started', 'id': ident,
                    'attempt': p['attempts'], 'time': time.monotonic()})
        if rejected:
            raise BudgetStop(rejected)

    @staticmethod
    def _pause(data, ident, reason):
        data['panel_paused'] = True
        data['events'].append({'event': 'panel_resource_paused', 'id': ident, 'reason': reason})

    @staticmethod
    def _known(usage):
        return all(isinstance(usage.get(k, 0), int) and not isinstance(usage.get(k, 0), bool)
                   and usage.get(k, 0) >= 0 for k in ('input_tokens', 'output_tokens')) and all(
            usage.get(k) is None or (isinstance(usage[k], int) and not isinstance(usage[k], bool)
                                    and usage[k] >= 0)
            for k in ('cache_read_input_tokens', 'cache_creation_input_tokens'))

    def usage(self, ident, usage):
        # Anthropic input_tokens excludes separate cache buckets. Report each
        # separately and cap their sum; this is processed-input accounting,
        # NOT a claim that all buckets have the same monetary rate.
        keys = ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')
        with self.transaction() as d:
            p = d['pending'][ident]
            u = {k: usage.get(k) for k in keys}
            p['usage_records'].append(u)
            d['events'].append({'event': 'provider_usage_received', 'id': ident, 'raw_usage': dict(usage)})
            if not self._known(u) or len(p['usage_records']) > p['attempts']:
                self._pause(d, ident, 'unreconciled_usage')
            elif (u['input_tokens'] + (u['cache_read_input_tokens'] or 0)
                  + (u['cache_creation_input_tokens'] or 0) > p['per_attempt_input_reserve']
                  or u['output_tokens'] > p['per_attempt_output_reserve']):
                p['reservation_breached'] = True
                self._pause(d, ident, 'actual_usage_exceeded_reservation')

    def finish(self, ident, error=None):
        blocked = False
        with self.transaction() as d:
            p = d['pending'].pop(ident)
            r = d['records'][self.record]
            elapsed = time.monotonic() - p['started']
            r['provider_seconds'][p['role']] += elapsed
            known = (len(p['usage_records']) == p['attempts']
                and all(self._known(u) for u in p['usage_records']))
            if not known:
                r['blocked'] = True
                self._pause(d, ident, 'sent_request_usage_unknown')
                # Forensic unresolved envelope, never silently released as zero.
                d.setdefault('unresolved', {})[ident] = p
            for u in p['usage_records']:
                # Add only observed valid portions. Missing buckets are still
                # unresolved, not evidence of zero total consumption.
                def portion(key):
                    value = u.get(key)
                    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
                read, write = portion('cache_read_input_tokens'), portion('cache_creation_input_tokens')
                inp, out = portion('input_tokens') + read + write, portion('output_tokens')
                r['input'] += inp; r['output'] += out
                r['cache_read'] += read; r['cache_write'] += write
                d['panel_input'] += inp; d['panel_output'] += out
            over = (r['input'] > self.limits['record_input'] or r['output'] > self.limits['record_output']
                or d['panel_input'] > self.limits['panel_input'] or d['panel_output'] > self.limits['panel_output'])
            if over:
                r['blocked'] = True
                self._pause(d, ident, 'actual_total_limit_exceeded')
            if p.get('reservation_breached'):
                r['blocked'] = True
            if r['provider_seconds'][p['role']] > self.limits[p['role'] + '_provider_seconds']:
                r['blocked'] = True
            blocked = r['blocked'] or d.get('panel_paused', False)
            d.setdefault('finished', {})[ident] = dict(p, error_type=error)
            d['events'].append({'event': 'logical_call_finished', 'id': ident,
                'record': self.record, 'purpose': p['purpose'], 'attempts': p['attempts'],
                'usage_known': known, 'exceeded_after_receipt': over,
                'reservation_breached': p.get('reservation_breached', False),
                'panel_paused': d.get('panel_paused', False),
                'elapsed_seconds': elapsed, 'error_type': error})
        return blocked
