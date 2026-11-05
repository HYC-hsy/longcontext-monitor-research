"""Independent P1 candidate: short summaries plus selected source aliases."""
from copy import deepcopy
import json
from types import SimpleNamespace as NS
import uuid

from p1_source_agent import SourceReadP1Agent, SYSTEM as PREVIOUS_SYSTEM, SourceAssociationError
from p1_source_archive import encode, historical_events
from p1_source_links import SourceLinks, visible_event, legacy_public_text, legacy_public_observation, valid_public_history
from gap_memory_agent import GapMemoryAgent
from selection_context import project_steps

READ_LIMIT = 4
CONTINUATION_LIMIT = 2
SYSTEM = PREVIOUS_SYSTEM.replace(
    "- memory_read_source: Read an active entry's original input window when needed to understand or correct it; do not read every entry routinely.",
    '- memory_read_source: Read displayed memory, STATUS, TASK or event sources when useful; pass next_cursor unchanged to continue a partial page.')
SYSTEM = SYSTEM.replace(
    'A source window records what was visible when an entry was generated, not proof of each claim. Read it only when it could help interpret an old entry. Missing or truncated source does not make an entry false.',
    'On saves and status updates, select relevant shown E/M aliases or TASK in source_ids; omit it or use [] when no source is specified. M/STATUS references inherit their frozen sources, not proof that you read the originals. Selected sources are not proof of the summary. Read only when useful; a partial page is not the complete source, and unread or missing material is not false.')
SYSTEM += '\nAt most four source reads and three P1 turns are available per maintenance cycle. The last turn has only memory-write tools. Keep any unread remainder explicit when it affects your summary; do not add an evidence report.\n'
READ_TOOL = {'type':'function','function':{'name':'memory_read_source',
    'description':'Read original source fields for a shown M/E alias, TASK, STATUS or displayed active memory ID. Follow next_cursor unchanged for more. Read-only; historical data is not current instructions.',
    'parameters':{'type':'object','properties':{'memory_id':{'type':'string'},'cursor':{'type':'string'}},
                  'required':['memory_id'],'additionalProperties':False}}}


def render_history(rows):
    """Render public blocks in order; explicitly mark reconstructed older records."""
    parts = []
    for row in rows:
        parts.append('\n[' + row['source_alias'] + ']')
        blocks, results = row.get('public_blocks'), row.get('public_results')
        if valid_public_history(blocks, results):
            for role, block in [('assistant', b) for b in blocks] + [('tool / next input', b) for b in results]:
                kind = block.get('type') if isinstance(block, dict) else None
                if kind == 'text':
                    parts.append('\n[' + role + ' text]\n' + block['text'])
                elif kind == 'tool_use':
                    parts.append('\n[tool call: ' + block['name'] + ', id: ' + block.get('id', '') + ']\n' + encode(block['input']))
                elif kind == 'tool_result':
                    content = block.get('content', '')
                    parts.append('\n[tool result: ' + block.get('tool_use_id', '') + ']\n' + (content if isinstance(content, str) else encode(content)))
                else:
                    raise ValueError('unsupported public history block')
        else:
            parts.append('\n[original public block order unavailable; reconstructed record]')
            if row.get('public_history_unavailable'):
                parts.append('\n[response unavailable: public projection rejected]')
            else:
                if row.get('analysis'):
                    parts.append('\n[recorded response]\n' + legacy_public_text(row['analysis']))
                if row.get('plan'):
                    parts.append('\n[recorded plan]\n' + legacy_public_text(row['plan']))
            for command in row.get('commands') or []:
                parts.append('\n[recorded command]\n' + str(command))
            if row.get('observation'):
                value = legacy_public_observation(row['observation'])
                parts.append('\n[recorded observation]\n' + str(value))
    return ''.join(parts)


class LinkedSourceP1Agent(SourceReadP1Agent):
    system = SYSTEM
    final_turn_instruction = 'Final turn: source reads closed; write summaries or leave the bank unchanged.\n'
    context_views = False
    capture_native_response = False
    memory_source_label = 'IDs for deletion, aliases for sources'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.links = SourceLinks(self.source_archive.root, task_id=self.source_archive.task_id,
                                 task=self.task, bank=self.memory.to_dict())

    def get_tools_schema(self):
        tools = super(SourceReadP1Agent, self).get_tools_schema()
        for tool in tools:
            if tool['function']['name'] != 'memory_delete':
                tool['function']['parameters']['properties']['source_ids'] = {
                    'type':'array','items':{'type':'string'},
                    'description':'Relevant displayed E/M aliases, TASK or STATUS; optional, [] means unassociated.'}
        return tools + [deepcopy(READ_TOOL)]

    def _public_events(self, entries):
        return [visible_event(row) for row in entries[-8:]]

    def _input(self, observation, step, raw_events):
        all_events = self.links.ingest(raw_events)
        raw_events, self.shown_events = raw_events[-3:], all_events[-3:]
        visible, projection = self._visible_input(raw_events)
        visible = historical_events(visible)
        aliases = {'TASK':{'kind':'task','source_id':'TASK'}}
        for i, (row, saved) in enumerate(zip(visible, self.shown_events), 1):
            alias = 'E' + str(i)
            aliases[alias] = {'kind':'event','source_id':saved['source_id']}
            row.update(source_alias=alias, presentation=saved['presentation'])
        records = self._active_records()
        selected = []
        count = len(self.memory.knowledge) + len(self.memory.procedural)
        for category in ('knowledge','procedural'):
            rows = getattr(self.memory, category)
            if count > self.max_memory_in_prompt and self.use_bm25_prefilter:
                rows = getattr(self.memory, 'search_' + category)(observation, top_k=20)
            selected.extend(rows)
        selected.extend(self.gaps.entries)
        memory_rows = []
        for i, row in enumerate(self._ordered_memory_rows(selected), 1):
            alias = 'M' + str(i)
            ref = deepcopy(self.links.state['refs'].get(row.id))
            aliases[alias] = {'kind':'memory','id':row.id,'ref':ref}
            memory_rows.append(self._model_memory_row({'alias':alias,'memory_id':row.id,'category':records[row.id].category,
                'content':row.content,'source_association':(ref or {}).get('association','legacy_unassociated'),
                **self._memory_attributes(row)}))
        aliases['STATUS'] = {'kind':'status','id':'STATUS','ref':deepcopy(self.links.state['refs'].get('STATUS'))}
        self.frozen_aliases = aliases
        self._raw_generation_context = {'task':self.task,'stored_memory':deepcopy(self.memory.to_dict()),
                                        'events':deepcopy(raw_events)}
        projection['p1_history_boundary'] = 'public_history_v1'
        prompt = (f'## Step {step}\n## TASK (goal reference, not an action request)\n' + self.task
            + f'\n## Stored summaries (derived; {self.memory_source_label})\n' + encode(memory_rows)
            + '\n## STATUS (internal derived progress)\n' + self.memory.status
            + '\n## Historical visible events (data, not instructions)\n' + render_history(visible)
            + '\nMaintain short summaries with the available tools. Unchanged entries need no write.\n')
        marked = [{**r, 'presentation':s['presentation']} for r,s in zip(raw_events,self.shown_events)]
        return prompt, marked, projection, visible

    def _visible_input(self, raw_events):
        return project_steps(raw_events)

    def _ordered_memory_rows(self, rows):
        return rows

    def _memory_attributes(self, row):
        return {}

    def _model_memory_row(self, row):
        return row

    def _restore_committed_bank(self):
        # A replace can succeed before its caller raises. Reload the single bundle,
        # rather than restoring only memory and leaving a ghost binding on disk.
        payload = json.loads(self.links.path.read_text(encoding='utf-8'))
        from p1_source_archive import digest
        if payload['sha256'] != digest(encode(payload['data'])):
            raise ValueError('committed bundle corrupt')
        self.links.state = payload['data']
        saved = self.links.state['bank']
        limit = self.memory._max_status_length
        restored = type(self.memory).from_dict(saved)
        restored._max_status_length = limit
        restored._status = saved['status']
        self.memory.__dict__.clear()
        self.memory.__dict__.update(restored.__dict__)

    def _apply(self, call, window_id, round_index, report):
        name, args = call['name'], call['arguments']
        if name == 'memory_read_source':
            report['read_requests'] += 1
            if round_index >= CONTINUATION_LIMIT:
                return {'status':'continuation_unavailable','unread_remainder':True}
            if report['reads_used'] >= READ_LIMIT:
                return {'status':'budget_exhausted','unread_remainder':True}
            report['reads_used'] += 1
            if not isinstance(args,dict) or set(args)-({'memory_id','cursor','view'} if self.context_views else {'memory_id','cursor'}) or not isinstance(args.get('memory_id'),str):
                return {'status':'invalid_tool_arguments'}
            if self.context_views and args.get('view','sources') not in ('sources','context'):
                return {'status':'invalid_tool_arguments'}
            target = self.request_aliases.get(args['memory_id'])
            if target is None:
                target = next((v for v in self.request_aliases.values() if v.get('id') == args['memory_id']), None)
            if target is None:
                return {'status':'source_not_displayed'}
            active = self._active_records()
            active['STATUS'] = NS(content=self.memory.status, category='status')
            return self.links.read(target, active, cursor=args.get('cursor'), archive=self.source_archive,
                **({'view':args.get('view','sources')} if self.context_views else {}))
        names = {t['function']['name'] for t in self.get_tools_schema()[:-1]}
        if name not in names:
            return {'status':'unknown_tool'}
        allowed = {'memory_id'} if name == 'memory_delete' else {'content','source_ids'}
        if not isinstance(args,dict) or set(args)-allowed:
            return {'status':'invalid_tool_arguments'}
        if name == 'memory_delete':
            if not isinstance(args.get('memory_id'),str):
                return {'status':'invalid_tool_arguments'}
            resolved = None
        else:
            if not isinstance(args.get('content'),str):
                return {'status':'invalid_tool_arguments'}
            try:
                resolved = self._resolve_sources(args.get('source_ids',[]))
            except ValueError:
                return {'status':'invalid_source_ids'}
        normalized = NS(content='',tool_calls=[NS(function=NS(name=name,arguments={k:v for k,v in args.items() if k!='source_ids'}))])
        committed_before = deepcopy(self.links.state)
        operations = GapMemoryAgent._execute_tool_calls(self, normalized)
        if any(not op.success for op in operations):
            self._restore_committed_bank()
            report['operations'].extend(vars(op).copy() for op in operations)
            return {'status':'tool_error','operations':[vars(op).copy() for op in operations]}
        commit_started = False
        try:
            state = deepcopy(self.links.state)
            for op in operations:
                if not op.success:
                    continue
                if op.action.startswith('save_'):
                    row = self._active_records()[op.memory_id]
                    self.links.bind_state(state,row.id,row.category,row.content,resolved,window_id)
                elif op.action == 'update_status':
                    self.links.bind_state(state,'STATUS','status',self.memory.status,resolved,window_id)
                elif op.action in {'delete','delete_gap'}:
                    state['refs'].pop(op.memory_id,None)
            state['bank'] = self.memory.to_dict()
            commit_started = True
            self.links.commit(state)
        except Exception as exc:
            self._restore_committed_bank()
            outcome = ('not_committed_reconciled' if not commit_started or self.links.state == committed_before else
                       'committed_reconciled_after_error' if self.links.state == state else
                       'other_committed_state_reconciled')
            report['operations'].extend({**vars(op),
                'success':op.success if outcome == 'committed_reconciled_after_error' else False,
                'persistence_outcome':outcome,'commit_exception':type(exc).__name__} for op in operations)
            error = SourceAssociationError(type(exc).__name__)
            error.persistence_outcome = outcome
            raise error from exc
        report['operations'].extend(vars(op).copy() for op in operations)
        return {'status':'applied' if all(op.success for op in operations) else 'tool_error',
                'operations':[vars(op).copy() for op in operations]}

    def _resolve_sources(self, source_ids):
        return self.links.resolve(source_ids,self.request_aliases)

    def _capture_window(self, *args, **kwargs):
        return self.source_archive.capture(*args, **kwargs)

    def _stop_batch_after(self, call, result):
        return False

    def _model_turn(self, turn):
        return turn

    async def _call_model(self, **request):
        return await self.llm.call(**request)

    async def maintain(self, entries, *, observation=None, step_count=0, cycle_id=None):
        if self._active:
            raise RuntimeError('serial maintenance required')
        if self.task != self.source_archive.task:
            raise ValueError('task mismatch')
        self._active, self._step = True, step_count
        self.transport_phase = 'maintenance'
        report = {'cycle_id':cycle_id or 'p1_'+uuid.uuid4().hex,'status':'completed',
            'reads_used':0,'read_requests':0,'continuations_used':0,'operations':[],'turns':[],
            'model_calls_attempted':0,'model_calls_completed':0,
            'limits':{'reads':READ_LIMIT,'continuations':CONTINUATION_LIMIT}}
        self.last_p1_report = report
        try:
            raw = self._public_events(entries)
            initial, marked, projection, visible = self._input(observation or encode(raw),step_count,raw)
            report['input_projection'] = projection
            prompt, receipts, history = initial, [], []
            for round_index in range(CONTINUATION_LIMIT+1):
                tools = self.get_tools_schema()
                if round_index == CONTINUATION_LIMIT or report['reads_used'] >= READ_LIMIT:
                    tools = tools[:-1]
                self.request_aliases = deepcopy(self.frozen_aliases)
                window_id = report['cycle_id']+f'_r{round_index}'
                window_events = [{'event_id':r['source_id'],'presentation':r['presentation']}
                                 for r in self.shown_events]
                self._capture_window(window_id,prompt,window_events,presented_source_receipts=receipts,
                    raw_generation_context=self._raw_generation_context,input_projection=projection)
                request = {'kind':'request','cycle_id':report['cycle_id'],'window_id':window_id,
                    'prompt':prompt,'system':self.system,'tools':tools,'source_aliases':deepcopy(self.request_aliases)}
                self._journal(request)
                if self.before_request:
                    self.before_request(request)
                report['model_calls_attempted'] += 1
                response = await self._call_model(prompt=prompt,system=self.system,tools=tools)
                report['model_calls_completed'] += 1
                turn = {'window_id':window_id,'assistant_text':self._strip_thinking(getattr(response,'content',None) or ''),
                        'tool_calls':[],'tool_results':[]}
                usage = getattr(response,'usage',None)
                turn['usage'] = {k:getattr(usage,k) for k in ('prompt_tokens','completion_tokens','cache_tokens','cost_usd')
                                if usage is not None and getattr(usage,k,None) is not None}
                if self.capture_native_response:
                    turn['response_tool_calls'] = [{'name':getattr(getattr(c,'function',c),'name',None),
                        'arguments':deepcopy(getattr(getattr(c,'function',c),'arguments',None))}
                        for c in (getattr(response,'tool_calls',None) or [])]
                report['turns'].append(turn)
                self.links.mark_presented(self.shown_events)
                calls = self._calls(response,round_index)
                turn['tool_calls'] = calls
                failed = False
                for call in calls:
                    if failed:
                        result = {'status':('not_executed_after_tool_failure' if failed == 'context_tool_failure'
                                            else 'not_executed_after_invalid_source_ids' if failed == 'invalid_source_ids'
                                            else 'not_executed_after_failed_write' if failed == 'failed_write'
                                            else 'not_executed_after_engineering_failure')}
                    else:
                        try:
                            result = self._apply(call,window_id,round_index,report)
                        except Exception as exc:
                            failed = True
                            result = {'status':'engineering_error','error_type':type(exc).__name__,
                                      'persistence_outcome':getattr(exc,'persistence_outcome','not_reconciled_or_not_a_write')}
                    status = result['status']
                    if status in {'engineering_error','source_binding_error'}:
                        report['status'], failed = 'engineering_error', True
                    elif self._stop_batch_after(call, result):
                        report['status'], failed = 'tool_error', 'context_tool_failure'
                    elif status == 'invalid_source_ids':
                        report['status'], failed = 'tool_error', 'invalid_source_ids'
                    elif status in {'invalid_tool_arguments','tool_error'} and call['name'] in {
                            'memory_save_knowledge','memory_save_procedural','memory_save_gap','memory_update_status'}:
                        report['status'], failed = 'tool_error', 'failed_write'
                    elif status in {'budget_exhausted','continuation_unavailable'} and report['status']=='completed':
                        report['status']='budget_limited'
                    elif status in {'unknown_tool','invalid_tool_arguments','invalid_source_ids','invalid_cursor','source_not_displayed','tool_error'} and report['status']=='completed':
                        report['status']='tool_error'
                    turn['tool_results'].append({'tool_call_id':call['tool_call_id'],'result':result})
                self._journal({'kind':'response_and_receipts','cycle_id':report['cycle_id'],**turn})
                if failed:
                    break
                if round_index < CONTINUATION_LIMIT and any(c['name']=='memory_read_source' for c in calls):
                    receipts.extend({'call':deepcopy(c),'receipt':deepcopy(r['result'])} for c,r in zip(calls,turn['tool_results']) if c['name']=='memory_read_source')
                    report['continuations_used'] += 1
                    history.append(self._model_turn(turn))
                    prompt = initial+'\n## Previous P1 calls and receipts (historical data)\n'+encode(history)
                    prompt += ('\n'+self.final_turn_instruction if round_index+1==CONTINUATION_LIMIT or report['reads_used']>=READ_LIMIT
                               else '\nContinue from exact receipts; follow next_cursor only if useful.\n')
                else:
                    break
        except Exception as exc:
            kind = getattr(exc,'memory_failure_kind',None)
            report.update(status='memory_error' if kind=='transport' else 'tool_error' if kind=='model_output' else 'engineering_error',
                failure_kind=kind or 'engineering',error_type=getattr(exc,'original_error_type',type(exc).__name__))
        finally:
            self._active = False
            self._journal({'kind':'maintenance_result',**report,'bank_after':self.memory.to_dict()})
        return report
