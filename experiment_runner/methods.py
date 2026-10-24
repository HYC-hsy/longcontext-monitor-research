"""Named adapters to legacy drivers, not a replacement GA plugin framework."""
from dataclasses import dataclass, replace

METHOD_PREFIXES = ('GA_STATEFUL_', 'GA_POS_', 'GA_PMA_UPSTREAM_',
                   'GA_MONITOR_', 'GA_M0_')
METHOD_EXTRA_KEYS = {'GA_PMA_ENABLED', 'GA_EXPERIMENT_TASK_TURNS',
                     'GA_TASK_DEADLINE_EPOCH'}


def clean_candidate_environment(inherited):
    """Return a clean subprocess environment; never mutate the caller's shell."""
    return {key: value for key, value in inherited.items()
            if key not in METHOD_EXTRA_KEYS and not key.startswith(METHOD_PREFIXES)}


@dataclass(frozen=True)
class Method:
    name: str
    condition: str
    research_candidate: str
    task_complete_response: bool = False
    task_turns_max: int | None = 300
    supports_runtime_policy: bool = False

    def runtime_environment(self, inherited=None):
        # The selected launcher enables exactly its bound method later. Do not
        # inherit a different method or an earlier episode's turn override.
        flags = ('GA_STATEFUL_MEMORY_ENABLED', 'GA_POS_ENABLED',
                 'GA_PMA_UPSTREAM_ENABLED', 'GA_PMA_ENABLED',
                 'GA_MONITOR_ENABLED', 'GA_M0_MONITOR_ENABLED',
                 'GA_POS_PMA_COMPLEMENT', 'GA_POS_PMA_SHARED_VIEW')
        stale = ({key: None for key in inherited
                  if key in METHOD_EXTRA_KEYS or key.startswith(METHOD_PREFIXES)}
                 if inherited is not None else {})
        return {**stale, **{flag: '0' for flag in flags},
                'GA_EXPERIMENT_TASK_TURNS': None,
                'GA_TASK_COMPLETE_RESPONSE': '1' if self.task_complete_response else None}

    def prepare_fields(self):
        return {'condition': self.condition,
                'research_candidate': self.research_candidate,
                'task_complete_response': self.task_complete_response}


_BUILTINS = (
    Method('ga-only', 'A', 'U'), Method('pma', 'B', 'U'),
    Method('pma-stateful', 'B', 'pma_stateful_memory_v1', True, None, True),
    Method('pma-gap', 'B', 'pma_gap_memory_v0', False, None, True),
    Method('pma-gap-evidence', 'B', 'pma_gap_evidence_v1', False, None, True),
    Method('pma-v1', 'B', 'V1'), Method('pma-d1', 'B', 'D1'),
    Method('pos', 'P', 'PoS', True),
    Method('pos-citation-fixed', 'P', 'PoS-citation-fixed', True),
    Method('pos-pma-complement', 'P', 'pos_pma_complement_v1', True),
    Method('pos-pma-shared-view', 'P', 'pos_pma_shared_view_v1', True))
_REGISTRY = {method.name: method for method in _BUILTINS}


def register(method: Method):
    """Register a named alias of a supported driver; new algorithms need drivers.

    An arbitrary candidate name must never silently dispatch to upstream PMA.
    """
    if type(method) is not Method or not isinstance(method.name, str) or not method.name or method.name in _REGISTRY:
        raise ValueError('method must have a unique nonempty name')
    if not any(replace(method, name=known.name) == known for known in _BUILTINS):
        raise ValueError('no installed legacy driver for requested method binding')
    _REGISTRY[method.name] = method


def resolve(name):
    try:
        return _REGISTRY[name]
    except (KeyError, TypeError):
        raise ValueError(f'unknown method: {name!r}') from None


def builtin_specs():
    return _BUILTINS


def get_method(method_id):
    return resolve(method_id)


def candidate_names(condition=None):
    return frozenset(m.research_candidate for m in _BUILTINS
                     if condition is None or m.condition == condition)


def validate_binding(condition, candidate):
    if not any(m.condition == condition and m.research_candidate == candidate
               for m in _BUILTINS):
        raise ValueError('unsupported method condition/candidate binding')
    return True
