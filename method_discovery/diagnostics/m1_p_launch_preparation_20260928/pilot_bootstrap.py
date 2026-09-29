"""Opt-in copied-bundle prelude. Does not edit frozen M1 or default checkout."""
import hashlib
import json
from pathlib import Path
import sys
import os

INSTALLED = False
INSTALLED_ROOT = None


def install(root):
    global INSTALLED, INSTALLED_ROOT
    root = Path(root).resolve()
    if INSTALLED:
        if INSTALLED_ROOT != root:
            raise RuntimeError('pilot bootstrap cannot switch source in one process')
        return
    binding = json.loads((root / 'pilot_binding.json').read_text(encoding='utf-8'))
    core = root / 'monitor_agent_core'
    for rel, digest in binding['monitor_files'].items():
        p = core / rel
        if hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise RuntimeError('frozen Monitor source mismatch: ' + rel)
    from monitor_agent_core.agent import MonitorAgent
    from monitor_agent_core.provider import MonitorProviderClient
    for name, module in list(sys.modules.items()):
        if name == 'monitor_agent_core' or name.startswith('monitor_agent_core.'):
            p = getattr(module, '__file__', None)
            if p and not Path(p).resolve().is_relative_to(core):
                raise RuntimeError('mixed Monitor import: ' + name)
    policy = None
    if binding['policy_enabled']:
        raw = (root / 'pilot_policy.txt').read_bytes()
        if hashlib.sha256(raw).hexdigest() != binding['policy_sha256']:
            raise RuntimeError('policy identity mismatch')
        policy = raw.decode('utf-8').strip()
    import experimental_adapter
    if (Path(experimental_adapter.__file__).resolve() != root / 'experimental_adapter.py'
            or hashlib.sha256((root / 'experimental_adapter.py').read_bytes()).hexdigest() != binding['adapter_sha256']):
        raise RuntimeError('experimental adapter source mismatch')
    apply_strategy = experimental_adapter.apply_strategy
    from resource_budget import ResourceBudget
    budget_path = os.environ.get('PILOT_BUDGET_PATH')
    record = os.environ.get('PILOT_RECORD_ID')
    budget_enabled = binding.get('budget_enabled', True)
    if budget_enabled and (not budget_path or not record):
        raise RuntimeError('explicit common budget path and record ID required')
    ledger = ResourceBudget(budget_path, record, binding['budget_limits']) if budget_enabled else None
    original = MonitorAgent.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        if not self.dcec_enabled or not self.semantic_continuity:
            raise RuntimeError('pilot requires native DCEC-v1 and semantic continuity')
        apply_strategy(self, policy)
        if ledger is not None:
            install_monitor_budget(self.client, ledger)
        self._progress('pilot_source_identity', monitor_commit=binding['monitor_commit'],
            task_commit=binding['task_commit'], imported_agent=str(sys.modules[MonitorAgent.__module__].__file__),
            policy_sha256=binding['policy_sha256'] if policy else None)
    MonitorAgent.__init__ = initialize
    INSTALLED = True
    INSTALLED_ROOT = root


def install_task(root):
    """Copied Task process entry: count the fixed native Claude path only."""
    install(root)
    import llmcore
    import threading
    import requests
    from resource_budget import ResourceBudget
    binding = json.loads((Path(root) / 'pilot_binding.json').read_text())
    if not binding.get('budget_enabled', True):
        return
    ledger = ResourceBudget(os.environ['PILOT_BUDGET_PATH'], os.environ['PILOT_RECORD_ID'], binding['budget_limits'])
    current = threading.local()
    raw = llmcore.NativeClaudeSession.raw_ask
    post, usage = requests.post, llmcore._record_usage

    def task_raw(self, messages):
        if self.model != 'claude-opus-4-8':
            raise RuntimeError('unexpected Task model')
        ident = ledger.begin('task', 'task', None, self.context_win, self.max_tokens or 8192)
        current.ident = ident
        error = None
        try:
            return (yield from raw(self, messages))
        except BaseException as exc:
            error = type(exc).__name__
            raise
        finally:
            blocked = ledger.finish(ident, error)
            current.ident = None
            if blocked and error is None:
                from resource_budget import BudgetStop
                raise BudgetStop('resource receipt unknown or over limit')

    def task_post(*args, **kwargs):
        ident = getattr(current, 'ident', None)
        if ident:
            ledger.attempt(ident)
        return post(*args, **kwargs)

    def task_usage(value, mode):
        ident = getattr(current, 'ident', None)
        if ident:
            if mode != 'messages':
                raise RuntimeError('unexpected Task usage format')
            ledger.usage(ident, value)
        return usage(value, mode)
    llmcore.NativeClaudeSession.raw_ask = task_raw
    requests.post, llmcore._record_usage = task_post, task_usage


def install_monitor_budget(client, ledger):
    """All native _request purposes share a logical budget; retries are attempts.

    Bound to a client, not a new model stage. Task budget integration is separate.
    """
    original_request, original_once = client._request, client._request_once
    current = {'id': None}

    def once(tools):
        ledger.attempt(current['id'])
        result = original_once(tools)
        ledger.usage(current['id'], result[1])
        return result

    def request(tools):
        ident = ledger.begin('monitor', getattr(client, 'request_purpose', 'review'),
            getattr(client, 'review_id', None), client.context_window, client.max_tokens)
        current['id'] = ident
        error = None
        try:
            return original_request(tools)
        except BaseException as exc:
            error = type(exc).__name__
            raise
        finally:
            blocked = ledger.finish(ident, error)
            current['id'] = None
            if blocked and error is None:
                from resource_budget import BudgetStop
                raise BudgetStop('resource receipt unknown or over limit')
    client._request_once, client._request = once, request
