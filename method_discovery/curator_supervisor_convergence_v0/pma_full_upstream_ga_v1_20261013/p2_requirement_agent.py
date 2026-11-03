"""Opt-in P2-only reader; original final alias selection and delivery stay verbatim."""
from copy import deepcopy
from p1_source_agent import SourceReadP1Agent
from p1_source_archive import encode, digest
from p1_requirements import model_turn
from bank_display_agent import BankDisplayAgent, SELECTION_SYSTEM
from p2_requirement_view import RequirementSelectionView
from selection_context import project_steps, render_selection
from tag_selection_contract import Item, parse_output, dispatch, delivery_json, diagnostic

READ_LIMIT, CONTINUATION_LIMIT = 4, 2
SYSTEM = SELECTION_SYSTEM + '''
You may decide directly from the initial displayed records, or optionally browse the frozen full active bank by fixed requirement, unclassified records, or flat view. P2 aliases remain stable throughout this selection. A partial record must be read completely before selecting it. Grouping is organization, not evidence or completion. memory_read_source reads selected sources or frozen context for already shown records; returned P2H handles are historical, not selectable records. Source and context pages are not semantic verification. At most four browse/source calls and two continuations are available; the last turn has no tools. Keep the original TASK/M alias output format, with no rewritten advice.
'''


class ResponseProtocolError(ValueError):
    pass


class RequirementSelectionAgent(BankDisplayAgent):
    system = SYSTEM
    delivery_protocol = 'verbatim-selection-v1'
    source_parameter = 'memory_id'
    upstream_error_semantics = False
    final_turn_instruction = 'Tools closed. Return the original TASK/M selection protocol or no_intervention.'
    final_output_error = 'final_turn_requires_original_selection_text'

    def __init__(self, *, p1, llm):
        super().__init__(task=p1.task,llm=llm,max_memory_in_prompt=p1.max_memory_in_prompt,
                         use_bm25_prefilter=p1.use_bm25_prefilter)
        self.p1 = p1
        self._selecting = False
        self.before_request = None
        self.last_p2_report = {}

    async def process(self, *args, **kwargs):
        raise RuntimeError('P2-only prototype: call select(); Task and P1 writes are not enabled')

    def tools(self):
        return [{'type':'function','function':{'name':'memory_browse',
            'description':'Read frozen full active records flat, by fixed requirement, or unclassified. Join record parts and JSON-decode; select its stable M alias only after the full record returns.',
            'parameters':{'type':'object','properties':{'view':{'type':'string','enum':['all','requirement','unclassified'],
                    'description':'Optional; defaults to all. requirement filters by fixed requirement text; unclassified has no requirement membership.'},
                'requirement':{'type':'string','description':'Required for view=requirement; use supplied fixed text. Omit for other views.'},
                'category':{'type':'string','enum':['knowledge','procedural','gap'],
                    'description':'Optional record-type filter in any view; omitted means all types. gap is a recorded need, not verified completion.'},
                'cursor':{'type':'string','description':'Pass next_cursor unchanged and repeat the same view, requirement and category filters.'}},'additionalProperties':False}}},
            {'type':'function','function':{'name':'memory_read_source',
            'description':'Read sources/context for a fully shown record, TASK, STATUS or returned P2H. Omitted view uses sources, falling back to context when unassociated. Continue with the same target and view choice. No memory writes.',
            'parameters':{'type':'object','properties':{'memory_id':{'type':'string',
                'description':'A fully shown P2 M label, TASK, STATUS or a returned history_handle (P2H...) from this session.'},
                'view':{'type':'string','enum':['sources','context']},'cursor':{'type':'string'}},
                'required':['memory_id'],'additionalProperties':False}}}]

    def _visible_steps(self, entries):
        return project_steps(entries)[0]

    def _prepare(self, observation, entries, step):
        view = RequirementSelectionView(self.p1)
        self.view = view
        bank = self.load_bank(deepcopy(view.links.state['bank']))
        self.memory, self.gaps, self.task = bank,bank,view.task
        # Reuse the real existing BM25/display capture; remap its IDs into the full P2 snapshot.
        BankDisplayAgent._build_phase2_prompt(self,observation,step)
        ids = {row.id for row in self._selection_snapshot.items}
        aliases = [alias for alias,row in view.aliases.items() if row.id in ids]
        self._selection_snapshot = view.snapshot
        self._active_selection_cycle = view.snapshot.cycle
        rows = [{'alias':'TASK','content':view.task}]+[
            {key:value for key,value in row.items() if key!='memory_id'} for row in view.initial_records(aliases)]
        steps = self._visible_steps(entries) if entries is not None else observation
        scope = 'all_frozen_active_records' if len(aliases)==len(view.items) else 'subset_of_frozen_active_records'
        initial = self._render_initial(rows,bank.status,steps,step,
            memory_note=('Initial catalogue scope: '+scope+'; tools can browse the frozen full active bank. '
                'Source ranges are selected/inherited event acceptance ordinals, not execution time or proof; '
                '[null,null] means unknown.'))
        initial += ('\n## Fixed requirements and initial memberships\n'+encode(view.groups(aliases))+
            '\nMembership lists cover only this initial catalogue, not hidden records. '
            'Use the supplied requirement text for optional full-bank browsing.\n'+
            '\nP2 full snapshot active record count: '+str(len(view.items))+'. Unclassified remains reachable.\n')
        return initial,aliases

    def _render_initial(self, *args, **kwargs):
        return render_selection(*args,**kwargs)

    def _response_calls(self, response, index, text):
        return SourceReadP1Agent._calls(self,response,index)

    def _read(self, call):
        name,args = call['name'],call['arguments']
        if name not in ('memory_browse','memory_read_source'):
            return {'status':'unknown_tool'}
        allowed = {'view','requirement','category','cursor'} if name=='memory_browse' else {'entry','memory_id','view','cursor'}
        if (not isinstance(args,dict) or set(args)-allowed or
                any(not isinstance(value,str) for value in args.values())):
            return {'status':'invalid_tool_arguments'}
        if name=='memory_browse':
            return self.view.browse(**args,model_view=True)
        if ('memory_id' in args)==('entry' in args) or args.get('view','sources') not in ('sources','context'):
            return {'status':'invalid_tool_arguments'}
        options = {key:value for key,value in args.items() if key not in ('entry','memory_id')}
        return self.view.read_source(memory_id=args.get('entry',args.get('memory_id')),
                                     alias_only='entry' in args,**options)

    def _finish(self, text, report):
        try:
            aliases,_,_ = parse_output(text)
            if any(alias not in self.view.seen for alias in aliases):
                raise ValueError('record_not_fully_shown')
            if not self.view.selection_valid(self.p1,aliases):
                raise ValueError(self.view.validation_error or 'snapshot_record_or_task_changed')
            active = {key:Item(row.id,'',row.category,row.content)
                      for key,row in self.p1._active_records().items()}
            outcome = dispatch(text,self.view.snapshot,completion_call_id=self.view.snapshot.call_id,
                active_cycle=self.view.snapshot.cycle,active_task_version=self.view.snapshot.task_version,
                active_records=active)
            report.update(diagnostic(outcome),status=outcome.kind,delivery=delivery_json(outcome),
                          selected_aliases=list(aliases))
        except ValueError as exc:
            report.update(status='selection_error',error=str(exc),failure_kind='model_output',delivery=None)
            if report['turns']:
                report['turns'][-1]['parse_error'] = str(exc)

    def pending_refs_valid(self):
        report,view = self.last_p2_report,getattr(self,'view',None)
        if (view is None or report.get('status')!='intervention' or
                report.get('snapshot_id')!=view.id):
            return False
        valid = view.selection_valid(self.p1,report['selected_aliases'])
        if not valid:
            report['delivery_revoked'] = True
            report['delivery_error'] = view.validation_error or 'snapshot_record_or_task_changed'
        return valid

    def _tool_failure_kind(self, result):
        return 'model_tool' if result['status'] in {
            'unknown_tool','invalid_tool_arguments','unknown_requirement','invalid_cursor',
            'record_not_yet_shown','source_not_in_snapshot_scope','invalid_history_handle',
            'ambiguous_memory_id'} else None

    async def select(self, *, observation='', entries=None, step_count=0):
        if self._selecting:
            raise RuntimeError('serial selection required')
        self._selecting = True
        self.transport_phase = 'selection'
        self.view = None
        report = {'status':'building','model_calls_attempted':0,'model_calls_completed':0,
            'tool_requests':0,'reads_used':0,'continuations_used':0,'turns':[],'delivery':None,
            'limits':{'reads':READ_LIMIT,'continuations':CONTINUATION_LIMIT,'logical_calls':3},
            'physical_provider_requests':'unknown; inherited client retries','persistent_writes':False}
        report['delivery_protocol'] = self.delivery_protocol
        self.last_p2_report = report
        stage = 'snapshot'
        try:
            initial,shown = self._prepare(observation,entries,step_count)
            report.update(snapshot_id=self.view.id,initial_aliases=shown,frozen_active_count=len(self.view.items),
                initial_scope='all_frozen_active_records' if len(shown)==len(self.view.items) else 'subset_of_frozen_active_records')
            report['entry_id_map'] = {alias:row.id for alias,row in self.view.aliases.items()}
            prompt, history = initial,[]
            for index in range(CONTINUATION_LIMIT+1):
                tools = self.tools() if index<CONTINUATION_LIMIT and report['reads_used']<READ_LIMIT else []
                request = {'prompt':prompt,'system':self.system,**({'tools':tools} if tools else {})}
                if self.before_request:
                    self.before_request(deepcopy(request))
                stage = 'model_call'
                report['model_calls_attempted'] += 1
                response = await self.llm.call(**request)
                report['model_calls_completed'] += 1
                text = self._strip_thinking(getattr(response,'content',None) or '')
                usage = getattr(response,'usage',None)
                turn = {'assistant_text':text,'tool_calls':[],'tool_results':[],
                    'prompt_sha256':digest(prompt),'system_sha256':digest(self.system),'tools_sha256':digest(encode(tools)),
                    'usage':{k:getattr(usage,k) for k in ('prompt_tokens','completion_tokens','cache_tokens','cost_usd')
                             if usage is not None and getattr(usage,k,None) is not None}}
                report['turns'].append(turn)
                stage = 'model_output'
                calls = self._response_calls(response,index,text)
                turn['tool_calls'] = calls
                if not calls:
                    self._finish(text,report)
                    break
                failed = None
                stage = 'tool_execution'
                for call in calls:
                    report['tool_requests'] += 1
                    if failed:
                        result = {'status':'not_executed_after_tool_failure'}
                    elif not tools or report['reads_used']>=READ_LIMIT:
                        result = {'status':'budget_exhausted'}
                    else:
                        report['reads_used'] += 1
                        result = self._read(call)
                        failed = self._tool_failure_kind(result)
                    turn['tool_results'].append({'tool_call_id':call['tool_call_id'],'result':result})
                if failed:
                    report.update(status='tool_error',failure_kind=failed)
                    break
                if index==CONTINUATION_LIMIT:
                    report['status'] = 'selection_error'
                    report['error'] = self.final_output_error
                    report['failure_kind'] = 'model_output'
                    break
                history.append(model_turn(turn,{row.id:alias for alias,row in self.view.aliases.items()},self.source_parameter))
                report['continuations_used'] += 1
                prompt = initial+'\n## Visible P2 calls and receipts (historical data)\n'+encode(history)
                if index+1==CONTINUATION_LIMIT or report['reads_used']>=READ_LIMIT:
                    prompt += '\n'+self.final_turn_instruction+'\n'
        except ResponseProtocolError as exc:
            report.update(status='selection_error',error=str(exc),failure_kind='model_output',delivery=None)
            if report['turns']:
                report['turns'][-1]['parse_error'] = str(exc)
        except Exception as exc:
            report.update(status='memory_error' if self.upstream_error_semantics and stage=='model_call' else 'engineering_error',
                failure_kind='transport' if stage=='model_call' else 'engineering',
                error_stage=stage,error_type=type(exc).__name__,delivery=None)
        finally:
            report['fully_shown_aliases'] = sorted(getattr(getattr(self,'view',None),'seen',()))
            self._selecting = False
        return report
