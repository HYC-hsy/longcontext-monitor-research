"""Offline optional-import doubles; production gate/episode/wrapper methods stay real."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import uuid

IMPORT_DOUBLES = []

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
for path in (STAGE, STAGE / 'vendor/pma_89e5c0d/src',
             STAGE / 'vendor/pma_89e5c0d/external/harbor/src'):
    sys.path.insert(0, str(path))


def module(name, **attrs):
    obj = ModuleType(name)
    obj.__dict__.update(attrs)
    sys.modules[name] = obj


# No dependencies are installed by this suite. These imports do not participate
# in the exercised execution path. Prefer installed dependencies when present.
if importlib.util.find_spec('regex') is None:
    IMPORT_DOUBLES.append('regex=re; ASCII/common-pattern fixtures only')
    import re
    sys.modules['regex'] = re  # ASCII fixtures use only the common regex subset.
if importlib.util.find_spec('rpds') is None:
    IMPORT_DOUBLES.append('rpds.HashTrieMap=copy-on-insert dict')
    class HashTrieMap(dict):
        def insert(self, key, value):
            out = type(self)(self)
            out[key] = value
            return out
    module('rpds', HashTrieMap=HashTrieMap)
if importlib.util.find_spec('shortuuid') is None:
    IMPORT_DOUBLES.append('shortuuid=stdlib uuid')
    module('shortuuid', uuid=lambda: uuid.uuid4().hex)
if importlib.util.find_spec('harbor') is None:
    IMPORT_DOUBLES.append('harbor import classes; actor/provider never constructed')
    for name in ('harbor', 'harbor.agents', 'harbor.agents.terminus_2',
                 'harbor.environments', 'harbor.llms', 'harbor.models', 'harbor.models.agent'):
        module(name)
    module('harbor.agents.terminus_2.terminus_2', Terminus2=type('Terminus2', (), {}), Command=str)
    module('harbor.environments.base', BaseEnvironment=object)
    module('harbor.llms.base', BaseLLM=object, LLMResponse=NS, ContextLengthExceededError=RuntimeError)
    module('harbor.llms.lite_llm', LiteLLM=object)
    module('harbor.models.agent.context', AgentContext=object)

from memory_agent.memory_enabled_agent import MemoryEnabledTerminus2
from memory_agent.memory.trigger import MemoryAgentTrigger, TriggerConfig
from latest_evidence_gap_store import LatestEvidenceGapMemory
from verbatim_selection_agent import VerbatimSelectionCitationGateAgent
from pma_evidence_review import claim_split_semantic as v4


def reply(calls=(), content='scripted'):
    import json
    return NS(content=content, tool_calls=[NS(function=NS(name=n, arguments=json.dumps(a)))
                                         for n, a in calls])


def wrapper(directory, *, repair=False, intervene=False):
    import json
    calls = []
    reviews = 0
    async def fake(**kw):
        nonlocal reviews
        phase = gate.transport_phase
        calls.append((phase, kw))
        if phase == 'maintenance':
            quotes = ['echo alpha', 'alpha-output'] if len(actor._accumulated_observations) > 1 else ['Synthetic task']
            return reply([('memory_save_knowledge', {'content': 'Observed alpha.',
                         'evidence': [{'quote': q} for q in quotes]})])
        if phase == 'selection':
            return reply(content='<intervene>TASK</intervene>' if intervene else '<no_intervention/>')
        if phase == 'citation_repair':
            return reply(content=json.dumps({'decision': 'replace', 'content': 'Observed alpha.',
                                            'evidence': [{'quote': 'Synthetic task'}]}))
        if kw['prompt'].startswith('TARGET TO DECOMPOSE'):
            return reply(content=json.dumps(['Observed alpha.']))
        reviews += 1
        verdict = 'insufficient' if repair and reviews == 1 else 'supported'
        return reply(content=json.dumps([['O', verdict, 'Scripted contract judgment.'],
                                       ['C1', verdict, 'Scripted limit.']] if verdict != 'supported'
                                      else [['O', verdict, 'Scripted support.'], ['C1', verdict]]))
    client = NS(call=fake, _model_name='offline-double')
    bank = LatestEvidenceGapMemory()
    gate = VerbatimSelectionCitationGateAgent(task='', memory=bank, llm=client,
                review_strategy=v4.STRATEGY, repair_limit=int(repair),
                review_directory=directory / 'review')
    actor = MemoryEnabledTerminus2.__new__(MemoryEnabledTerminus2)
    actor.__dict__.update(_memory=bank, _memory_agent=gate, _memory_llm=client,
        _research_candidate='pma_gap_evidence_v1', _trigger=MemoryAgentTrigger(TriggerConfig(interval=1, trigger_on_first_step=True)),
        _reset_status_on_episode=True, _reset_knowledge_on_episode=False, _reset_procedural_on_episode=False,
        _accumulated_observations=[], _sliding_window_size=8, _memory_trajectory_steps=[],
        _memory_trigger_count=0, _memory_operation_count=0, _injection_count=0, _noop_count=0,
        _memory_step_in_episode=0, _snapshot_dir=None, _environment=None,
        _pending_injection=None, _injection_used=False)
    return actor, calls
