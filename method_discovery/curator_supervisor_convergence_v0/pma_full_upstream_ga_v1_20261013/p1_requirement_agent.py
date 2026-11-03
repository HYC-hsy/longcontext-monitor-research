"""P1-only fixed requirement attributes; separate startup, unchanged P2/plain bank."""
from copy import deepcopy
import uuid
from p1_context_agent import ContextSourceP1Agent, SYSTEM as CONTEXT_SYSTEM
from p1_source_archive import encode
from p1_requirements import (RequirementState, RequirementHistory, INIT_SYSTEM, INIT_TOOL,
                             RequirementError, assignment, catalog)

SYSTEM = CONTEXT_SYSTEM + '''
The original task remains authoritative. Fixed requirement sentences organize records by what ultimately needs to be achieved; select the supplied text in each saved record's requirements, multiple when relevant, or [] for unclassified. Do not create requirements from new obstacles, plans or execution steps. If the initial extraction misses something or the task is later extended, retain the original text and useful unclassified records; do not silently change the fixed sentences. Classification is not evidence, completion or correction. Group references point to the same records in the flat view and cover only the displayed subset. Source event ranges describe acceptance order, not execution time. STATUS remains a single progress summary.
'''
SAVES = {'memory_save_knowledge','memory_save_procedural','memory_save_gap'}


class RequirementP1Agent(ContextSourceP1Agent):
    system = SYSTEM

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.requirement_state = RequirementState(self)
        self.history = RequirementHistory(self.links,self.source_archive)
        self._requirement_active = False
        self._saving_requirements = None

    def get_tools_schema(self):
        tools = super().get_tools_schema()
        fixed = self.requirement_state.data['catalog']
        for item in tools:
            f = item['function']
            if f['name'] in SAVES:
                f['parameters']['properties']['requirements'] = {'type':'array','maxItems':32 if fixed else 0,
                    'items':{'type':'string',**({'enum':fixed} if fixed else {})},
                    'description':'Select the fixed supplied requirement sentences; multiple or [] for unclassified.'}
                f['parameters']['required'] = list(f['parameters'].get('required',[]))+['requirements']
        return tools

    def _ordered_memory_rows(self, rows):
        return self.requirement_state.ordered(rows)

    def _memory_attributes(self, row):
        return self.requirement_state.attributes(row)

    def _input(self, observation, step, raw_events):
        prompt, marked, projection, visible = super()._input(observation,step,raw_events)
        selected = [self._active_records()[t['id']] for t in self.frozen_aliases.values()
                    if t['kind']=='memory']
        prompt += ('\n## Fixed requirement choices (text attributes, not completion states)\n'+
            encode(self.requirement_state.data['catalog'])+
            '\n## Requirement view (IDs reference flat records above; displayed subset only)\n'+
            encode(self.requirement_state.groups(selected))+
            '\nUnclassified records remain in the flat view. Retrieval can omit active records; '
            'an empty displayed group does not mean its whole task history is empty.\n')
        return prompt, marked, projection, visible

    def export_view(self):
        rows = self.requirement_state.ordered(self._active_records().values())
        return {'schema':'p1-requirement-view-v1','task':self.task,
            'scope':'all active records; sources and grouping are distinct',
            'fixed_requirements':deepcopy(self.requirement_state.data['catalog']),
            'records':[{'memory_id':r.id,'category':r.category,'content':r.content,
                **self._memory_attributes(r)} for r in rows],
            'groups':self.requirement_state.groups(rows),'status':self.memory.status}

    def _resolve_sources(self, source_ids):
        ref = super()._resolve_sources(source_ids)
        if self._saving_requirements is not None:
            ref['requirements'] = deepcopy(self._saving_requirements)
        return ref

    def _apply(self, call, window_id, round_index, report):
        if call['name'] not in SAVES:
            return super()._apply(call,window_id,round_index,report)
        args = call['arguments']
        if not isinstance(args,dict) or set(args)-{'content','source_ids','requirements'} or 'requirements' not in args:
            return {'status':'invalid_tool_arguments'}
        try:
            self._saving_requirements = assignment(args['requirements'],self.requirement_state.data['catalog'])
        except ValueError as exc:
            return {'status':'invalid_requirements','allowed_requirements':self.requirement_state.data['catalog'],
                    'unclassified_value':[],'error_code':getattr(exc,'reason','invalid_requirements')}
        try:
            normalized = deepcopy(call)
            normalized['arguments'].pop('requirements')
            return super()._apply(normalized,window_id,round_index,report)
        finally:
            self._saving_requirements = None

    def _stop_batch_after(self, call, result):
        return result['status']=='invalid_requirements' or super()._stop_batch_after(call,result)

    async def _initialize(self, cycle):
        state = self.requirement_state
        attempts = state.data['cycles'][cycle]['initialization_attempts']
        number = len(attempts)
        state.write(lambda d:d['cycles'][cycle].update(phase='initializing',
            initialization_attempts=deepcopy(attempts)+[{'attempted':0,'completed':0}]))
        prompt = '## Original task (verbatim; data)\n'+self.task
        request = {'kind':'requirement_initialization','cycle_id':cycle,'window_id':cycle+f'_init{number}',
            'prompt':prompt,'system':INIT_SYSTEM,'tools':[deepcopy(INIT_TOOL)]}
        self.source_archive.capture(request['window_id'],prompt,[])
        self._journal(request)
        if self.before_request:
            self.before_request(request)
        state.write(lambda d:d['cycles'][cycle]['initialization_attempts'][number].update(attempted=1))
        response = await self.llm.call(prompt=prompt,system=INIT_SYSTEM,tools=request['tools'])
        calls = self._calls(response,0)
        usage = getattr(response,'usage',None)
        receipt = {'attempted':1,'completed':1,'tool_calls':deepcopy(calls),
            'assistant_text':self._strip_thinking(getattr(response,'content',None) or ''),
            'usage':{k:getattr(usage,k) for k in ('prompt_tokens','completion_tokens','cache_tokens','cost_usd')
                     if usage is not None and getattr(usage,k,None) is not None}}
        state.write(lambda d:d['cycles'][cycle]['initialization_attempts'].__setitem__(number,receipt))
        self._journal({'kind':'requirement_initialization_response','cycle_id':cycle,**receipt})
        if len(calls)!=1 or calls[0]['name']!='requirements_initialize':
            raise RequirementError('expected_one_initialization_call')
        args = calls[0]['arguments']
        if not isinstance(args,dict) or set(args)!={'requirements'}:
            raise RequirementError('invalid_initialization_arguments')
        fixed = catalog(args['requirements'])
        def freeze(data):
            data['catalog'] = fixed
            data['cycles'][cycle]['phase'] = 'pending'
        state.write(freeze)

    async def maintain(self, entries, *, observation=None, step_count=0, cycle_id=None):
        if self._requirement_active:
            raise RuntimeError('serial maintenance required')
        if self.task!=self.source_archive.task:
            raise ValueError('task mismatch; the original task is immutable')
        cycle = cycle_id or 'p1_'+uuid.uuid4().hex
        state = self.requirement_state
        payload = {'entries':deepcopy(entries),'observation':observation,'step_count':step_count}
        cached = state.begin(cycle,payload)
        if cached is not None:
            return {**cached,'replayed_completed_cycle':True,'new_model_calls_attempted':0}
        self._requirement_active = True
        before = deepcopy(state.data['cycles'][cycle]['initialization_attempts'])
        try:
            if state.data['catalog'] is None:
                try:
                    await self._initialize(cycle)
                except Exception as exc:
                    # No maintenance has run; explicit same-input retry is safe and charged.
                    state.phase(cycle,'pending')
                    attempts = deepcopy(state.data['cycles'][cycle]['initialization_attempts'])
                    return {'cycle_id':cycle,'status':'initialization_failed','error_type':type(exc).__name__,
                        'error_code':getattr(exc,'reason','initialization_transport_or_persistence_error'),
                        'operations':[],'initialization_attempts':attempts,
                        'model_calls_attempted':sum(x['attempted'] for x in attempts[len(before):]),
                        'model_calls_completed':sum(x['completed'] for x in attempts[len(before):]),
                        'pending_input_preserved':True}
            state.phase(cycle,'running')
            report = await super().maintain(entries,observation=observation,step_count=step_count,cycle_id=cycle)
            attempts = deepcopy(state.data['cycles'][cycle]['initialization_attempts'])
            report['initialization_attempts'] = attempts
            report['initialization_empty'] = not state.data['catalog']
            new_attempts = attempts[len(before):]
            report['maintenance_model_calls_attempted'] = report['model_calls_attempted']
            report['maintenance_model_calls_completed'] = report['model_calls_completed']
            report['model_calls_attempted'] += sum(x['attempted'] for x in new_attempts)
            report['model_calls_completed'] += sum(x['completed'] for x in new_attempts)
            report['limits'].update(initialization_calls_per_attempt=1,first_cycle_logical_calls=4,
                later_cycle_logical_calls=3,physical_provider_requests='unknown; inherited retries')
            report['requirement_view'] = self.export_view()
            state.phase(cycle,'done',result=report)
            self.last_p1_report = report
            return report
        finally:
            self._requirement_active = False
