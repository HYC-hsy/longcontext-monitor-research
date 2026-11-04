"""Fixed task requirements and crash checkpoints in the existing atomic bundle."""
from copy import deepcopy
import json
import re
import unicodedata
from p1_source_archive import encode, digest
from p1_context_history import InputMemoryHistory

KEY = 'requirement_attributes_v1'
GENERAL_TOPIC = 'General'


def topics(fixed):
    """Fixed task-derived topics plus the host-provided general topic."""
    return list(dict.fromkeys([*(fixed or []), GENERAL_TOPIC]))


def model_turn(turn, aliases=None, source_parameter='memory_id'):
    """Visible conversation only; retain full diagnostics/legacy fields in the log."""
    visible = {key:deepcopy(turn[key]) for key in ('assistant_text','tool_calls','tool_results')}
    aliases = aliases or {}
    for call in visible['tool_calls']:
        args = call['arguments']
        if call['name'] in ('memory_read_source','memory_delete') and isinstance(args,dict) and 'memory_id' in args:
            value = args['memory_id']
            args['memory_id'] = aliases.get(value,value)
            if source_parameter!='memory_id':
                args[source_parameter] = args.pop('memory_id')
    for item in visible['tool_results']:
        receipt = item.get('result',{})
        if 'page_sequence_complete' in receipt:
            receipt.pop('complete',None)
        receipt.pop('target_resolution',None)
        receipt.pop('historical_memory_id',None)
        if 'target' in receipt:
            if str(receipt['target']).startswith('P2_BROWSE_'):
                receipt.pop('target')
            else:
                receipt['target'] = aliases.get(receipt['target'],receipt['target'])
        for operation in receipt.get('operations',[]):
            key = operation.pop('memory_id',None)
            if key in aliases:
                operation['entry'] = aliases[key]
        for part in receipt.get('parts',[]):
            if part['field']=='input_memory' and part['start']==0 and part['end']==part['total']:
                # Atomic directory protocol JSON; original evidence text is never rewritten.
                data = json.loads(part['text'])
                data.pop('memory_id',None)
                part['text'] = encode(data)
                part['end'] = part['total'] = len(part['text'])
    return visible


INIT_SYSTEM = '''Organize the original task into fixed memory topics by work objective, not by the order of its instructions. Group each outcome with its supporting steps, files, checks and constraints; split only when work has a distinct purpose and benefits from independently retrieved memories. For example, “prepare, save and check a report” is one topic: “produce a checked report”, not three topics for the steps.

Describe each objective concisely and attach its explicit prohibitions, preserving their scope. Keep required, recommended and optional details distinct; do not invent or strengthen requirements or treat examples as exhaustive. Compress supporting details, not task boundaries; the original task remains authoritative.

Before submitting, check that no topic merely repeats a step or condition of another, that important prohibitions are retained, and that suggestions remain optional. Keep each topic within 512 characters and all topics within 2048 characters. Use only the original task, not later plans or obstacles. Use requirements_initialize once; use [] only when no task requirement can be identified. Do not create a General topic; the host supplies it. This organizes memory; it does not solve or evaluate the task.'''
INIT_TOOL = {'type':'function','function':{'name':'requirements_initialize',
    'description':'Propose fixed task topics; at most 32 unique topics, 512 characters each, 2048 total. No record IDs or completion states.',
    'parameters':{'type':'object','properties':{'requirements':{'type':'array','maxItems':32,
        'items':{'type':'string','maxLength':512}}},'required':['requirements'],'additionalProperties':False}}}

def upstream_observation(task, entries):
    """Reuse PMA's exact task + eight-step BM25 context, separate from evidence IDs."""
    from types import SimpleNamespace
    from memory_agent.memory_enabled_agent import MemoryEnabledTerminus2
    rows = deepcopy(entries[-8:])
    for index,row in enumerate(rows):
        row.setdefault('step',index+2)
        if row.get('commands'):
            row['commands'] = [str(c) for c in row['commands']]
    state = SimpleNamespace(_task_description=task,_sliding_window_size=8,
        _accumulated_observations=[{'step':1,'observation':task}]+rows,
        _format_step_entry=MemoryEnabledTerminus2._format_step_entry)
    return MemoryEnabledTerminus2._get_memory_agent_context(state)


class MemoryModelError(RuntimeError):
    def __init__(self, error, kind):
        self.memory_failure_kind = kind
        self.original_error_type = type(error).__name__
        super().__init__(str(error))


class RequirementError(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def canonical(text):
    if not isinstance(text,str):
        raise RequirementError('requirement_not_text')
    value = unicodedata.normalize('NFC',text.replace('\r\n','\n').replace('\r','\n')).strip()
    if not value or len(value)>512 or any(unicodedata.category(c)=='Cc' and c!='\n' for c in value):
        raise RequirementError('empty_oversized_or_control_character_text')
    return value


def catalog(values):
    if not isinstance(values,list) or len(values)>32:
        raise RequirementError('invalid_requirement_list')
    result = [canonical(x) for x in values]
    if len(result)!=len(set(result)):
        raise RequirementError('duplicate_requirement')
    if sum(map(len,result))>2048:
        raise RequirementError('oversized_catalog')
    return result


def assignment(values, fixed):
    if not isinstance(values,list) or len(values)>33:
        raise RequirementError('invalid_requirement_assignment')
    available = topics(fixed)
    chosen = {canonical(x) for x in values}
    if chosen-set(available):
        raise RequirementError('unknown_requirement_choose_supplied_text')
    # Empty selection is safely retained as General rather than dropping memory.
    if not chosen:
        chosen = {GENERAL_TOPIC}
    return [x for x in available if x in chosen]


class RequirementHistory(InputMemoryHistory):
    def coverage(self, records, receipts):
        normalized = deepcopy(receipts)
        for item in normalized:
            args = item.get('call',{}).get('arguments',{})
            if isinstance(args,dict) and 'entry' in args:
                args['memory_id'] = args.pop('entry')
        return super().coverage(records,normalized)

    def _requirements(self, row):
        return deepcopy((row['ref'] or {}).get('requirements',[]))

    def _record_attributes(self, row):
        # The ref is frozen together with the body; never consult current active metadata.
        values = self._requirements(row)
        attributes = {'requirements':values}
        # A directory JSON string is escaped again inside its page's text field.
        # Bound that wire representation, leaving room for metadata + a whole grant item.
        if len(encode({'text':encode(attributes)})) <= 2500:
            return attributes
        return {'requirements_paged':True,'requirements_count':len(values),
                'requirements_sha256':digest(encode(values)),
                'requirements_location':'Read this H handle; join requirements parts, then JSON-decode.'}

    def _historical_fields(self, row):
        if self._record_attributes(row).get('requirements_paged'):
            return [('history','requirements','json_value',encode(self._requirements(row)))]
        return []


class RequirementState:
    def __init__(self, agent):
        self.agent, self.links = agent, agent.links
        state = deepcopy(self.links.state)
        if KEY not in state:
            bank = state['bank']
            if state['refs'] or state['events'] or any(bank[k] for k in ('knowledge','procedural','gaps','status')):
                raise ValueError('new candidate requires an empty new-task bank; no migration')
            state[KEY] = {'schema':KEY,'task_sha256':digest(agent.task),'catalog':None,'cycles':{}}
            self.links.commit(state)
        data = self.data
        if data['schema']!=KEY or data['task_sha256']!=digest(agent.task):
            raise ValueError('requirement task mismatch')
        if data['catalog'] is not None and catalog(data['catalog'])!=data['catalog']:
            raise ValueError('invalid frozen catalog')
        for ref in self.links.state['refs'].values():
            if ref['category']!='status' and assignment(ref.get('requirements'),data['catalog'] or [])!=ref['requirements']:
                raise ValueError('invalid stored requirement assignment')

    @property
    def data(self):
        return self.links.state[KEY]

    def write(self, mutate):
        state = deepcopy(self.links.state)
        mutate(state[KEY])
        # Reconcile even os.replace-success-then-error, as the existing write path does.
        try:
            self.links.commit(state)
        except BaseException:
            self.agent._restore_committed_bank()
            raise

    def begin(self, cycle, payload):
        if not isinstance(cycle,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,90}',cycle):
            raise ValueError('cycle_id must be 1..90 safe characters')
        sha = digest(encode(payload))
        previous = self.data['cycles'].get(cycle)
        if previous:
            if previous['input_sha256']!=sha:
                raise ValueError('cycle input changed')
            if previous['phase']=='done':
                return deepcopy(previous['result'])
            if previous['phase'] in ('running','abandoned'):
                raise RuntimeError('recovery_required; inspect partial commits and acknowledge interruption')
        for key,item in self.data['cycles'].items():
            if key!=cycle and item['phase'] not in ('done','abandoned'):
                raise RuntimeError('pending cycle must be resolved first')
        if previous is None:
            self.write(lambda d:d['cycles'].update({cycle:{'phase':'pending','input_sha256':sha,
                'input':deepcopy(payload),'initialization_attempts':[]}}))
        return None

    def phase(self, cycle, phase, **values):
        self.write(lambda d:d['cycles'][cycle].update(phase=phase,**deepcopy(values)))

    def acknowledge_interrupted(self, cycle):
        """Host-only recovery: never replay writes; a fresh cycle may use the committed bank."""
        if self.data['cycles'][cycle]['phase']!='running':
            raise ValueError('only uncertain interrupted maintenance needs acknowledgement')
        self.phase(cycle,'abandoned')

    def event_span(self, key):
        ref = self.links.state['refs'].get(key) or {}
        order = {sid:i+1 for i,sid in enumerate(self.links.state['events'])}
        sources = ref.get('sources',[])
        positions = [order[s['source_id']] for s in sources if s.get('source_id') in order]
        return {'kind':'accepted_event_range' if positions else 'unknown',
                'first':min(positions) if positions else None,'last':max(positions) if positions else None,
                'meaning':'selected/inherited source acceptance order; not execution time or claim support'}

    def attributes(self, row):
        return {'requirements':deepcopy(self.links.state['refs'][row.id]['requirements']),
                'source_event_order':self.event_span(row.id)}

    def ordered(self, rows):
        unique = {row.id:row for row in rows}
        return sorted(unique.values(),key=lambda r:(self.event_span(r.id)['first'] is None,
            self.event_span(r.id)['first'] or 0,self.event_span(r.id)['last'] or 0,r.id))

    def groups(self, rows):
        rows = self.ordered(rows)
        result = [{'requirement':text,'memory_ids':[r.id for r in rows if text in
            self.links.state['refs'][r.id]['requirements']]} for text in topics(self.data['catalog'])]
        return {'requirements':result,'unclassified_memory_ids':[r.id for r in rows if not
            self.links.state['refs'][r.id]['requirements']]}
