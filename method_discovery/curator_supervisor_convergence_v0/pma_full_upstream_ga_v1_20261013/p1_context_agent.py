"""Opt-in generation-context consumer; no changes to memory write policy."""
from copy import deepcopy
from types import SimpleNamespace as NS
from p1_source_archive import digest, encode
from p1_context_history import InputMemoryHistory, HistoryError, PREFIX
from p1_linked_agent import LinkedSourceP1Agent, SYSTEM as LINKED_SYSTEM, READ_LIMIT, CONTINUATION_LIMIT

GAP_DESCRIPTION = ('Record task-relevant conditions still to satisfy or questions still to answer. '
    'Keep failure details in experiences, not gaps; gaps are not guessed causes or action plans. '
    'Knowing a failure or clearing another blocker does not resolve the open condition.')
OLD_GAP = ('Record task-relevant unmet or unverified conditions, based on task requirements or observations. '
    'Keep unresolved parts when a blocker clears; close only what is resolved or no longer applies.')
SYSTEM = LINKED_SYSTEM.replace(
    'select relevant shown E/M aliases or TASK in source_ids',
    'select relevant shown E/M aliases, TASK, STATUS or returned H1 handles in source_ids')
SYSTEM = SYSTEM.replace('M/STATUS references inherit their frozen sources',
                        'M/STATUS/H1 references inherit their frozen sources')
SYSTEM = SYSTEM.replace(OLD_GAP,GAP_DESCRIPTION).replace(
    'Track current progress and relevant next steps internally, not for the action agent.',
    'Track current progress internally, not for the action agent.')
SYSTEM += ('\nOmitting view reads selected sources, or frozen context when none are linked; explicit views stay strict. '
    'Input-memory directories describe generation input, not claim evidence. Returned H1 handles are read-only '
    'and may be used in source_ids; read them only when useful.\n')


class ContextSourceP1Agent(LinkedSourceP1Agent):
    system = SYSTEM
    context_views = True
    memory_source_label = 'memory IDs or M aliases for reading/deletion'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history = InputMemoryHistory(self.links,self.source_archive)

    def get_tools_schema(self):
        tools = super().get_tools_schema()
        delete = next(t['function'] for t in tools if t['function']['name']=='memory_delete')
        delete['description'] += ' Accepts a frozen displayed M alias or its displayed memory ID; never E/TASK/STATUS or H1 history handles.'
        for item in tools[:-1]:
            function = item['function']
            if function['name']=='memory_save_gap':
                function['description'] = ('Save a task-relevant condition still to satisfy or question still to answer; '
                    'not a failure log, guessed cause or action plan.')
            props = function['parameters']['properties']
            if 'source_ids' in props:
                props['source_ids']['description'] += ' Returned H1 history handles may also be cited.'
        tool = tools[-1]['function']
        tool['description'] += (' Omit view to use selected sources, falling back to frozen context only when no sources are linked. '
            'Explicit views are strict. Returned H1 handles read frozen historical records, not current instructions. '
            'Continue a cursor with the same view choice, including omission.')
        tool['parameters']['properties']['view'] = {
            'type':'string', 'enum':['sources','context']}
        return tools

    def _input(self, observation, step, raw_events):
        prompt, marked, projection, visible = super()._input(observation, step, raw_events)
        displayed = {t['id'] for t in self.frozen_aliases.values() if t['kind']=='memory'}
        self._context_records = {key: {
            'content_sha256':digest(row.content), 'category':row.category,
            'ref':deepcopy(self.links.state['refs'].get(key))}
            for key,row in self._active_records().items() if key in displayed}
        active = self._active_records()
        self._input_history_records = [self.history.record(key,active[key].category,active[key].content,
            self._context_records[key]['ref']) for key in self._context_records]
        if self.memory.status or self.frozen_aliases['STATUS']['ref']:
            self._input_history_records.append(self.history.record('STATUS','status',self.memory.status,
                self.frozen_aliases['STATUS']['ref']))
        return prompt, marked, projection, visible

    def _resolve_target(self, value, *, deleting):
        candidates = []
        if value in self.request_aliases:
            candidates.append(self.request_aliases[value])
        candidates.extend(t for t in self.request_aliases.values()
                          if t.get('kind') == 'memory' and t.get('id') == value)
        frozen = self._context_records
        unique = {encode(t):t for t in candidates}
        resolution = {'resolved_memory_id':None}
        if not unique:
            return None, {**resolution, 'status':'source_not_displayed'}
        if len(unique) != 1:
            return None, {**resolution, 'status':'ambiguous_memory_id'}
        target = next(iter(unique.values()))
        if target['kind'] != 'memory':
            return (None, {**resolution, 'status':'invalid_delete_target'}) if deleting else (target, resolution)
        key = target['id']
        resolution['resolved_memory_id'] = key
        row = self._active_records().get(key)
        if row is None:
            return None, {**resolution, 'status':'entry_not_found'}
        binding = frozen.get(key)
        if (binding is None or digest(row.content) != binding['content_sha256'] or
                row.category != binding['category'] or
                self.links.state['refs'].get(key) != binding['ref'] or
                target.get('ref') != binding['ref']):
            return None, {**resolution, 'status':'memory_target_changed'}
        return target, resolution

    def _resolve_sources(self, source_ids):
        resolved = super()._resolve_sources(source_ids)
        # _apply has validated each H1 grant before reaching this binding hook.
        cited = list(dict.fromkeys(token for token in source_ids if token.startswith(PREFIX)))
        if cited:
            resolved['cited_history_handles'] = cited
        return resolved

    def _capture_window(self, *args, **kwargs):
        kwargs['input_memory_coverage'] = self.history.coverage(
            self._input_history_records,kwargs.get('presented_source_receipts',()))
        return super()._capture_window(*args, **kwargs)

    def _history_collision(self, token):
        return token in self.request_aliases or any(
            t.get('id')==token for t in self.request_aliases.values() if t['kind']=='memory')

    def _apply(self, call, window_id, round_index, report):
        name, args = call['name'], call['arguments']
        if name not in {'memory_read_source','memory_delete'}:
            aliases = self.request_aliases
            try:
                cited = args.get('source_ids',[]) if isinstance(args,dict) else []
                if isinstance(cited,list):
                    extended = deepcopy(aliases)
                    for token in cited:
                        if isinstance(token,str) and token.startswith(PREFIX):
                            if self._history_collision(token):
                                return {'status':'invalid_source_ids'}
                            row = self.history.load(token)
                            extended[token] = {'kind':'memory','id':row['memory_id'],'ref':row['ref']}
                    self.request_aliases = extended
                return super()._apply(call,window_id,round_index,report)
            except HistoryError as exc:
                return {'status':'invalid_source_ids' if exc.status=='invalid_history_handle' else 'source_binding_error'}
            finally:
                self.request_aliases = aliases
        allowed = {'memory_id'} if name == 'memory_delete' else {'memory_id','view','cursor'}
        if (not isinstance(args,dict) or set(args)-allowed or
                not isinstance(args.get('memory_id'),str) or
                (name == 'memory_read_source' and args.get('view','sources') not in ('sources','context'))):
            return super()._apply(call,window_id,round_index,report)
        if name == 'memory_read_source' and (round_index >= CONTINUATION_LIMIT or report['reads_used'] >= READ_LIMIT):
            return super()._apply(call,window_id,round_index,report)
        token = args['memory_id']
        is_history = token.startswith(PREFIX)
        if is_history:
            error = 'ambiguous_memory_id' if self._history_collision(token) else (
                'historical_read_only' if name=='memory_delete' else None)
            target, resolution = None, {'resolved_memory_id':None}
        else:
            target, resolution = self._resolve_target(token,deleting=name=='memory_delete')
            error = resolution.get('status') if target is None else None
        if name == 'memory_read_source':
            report['read_requests'] += 1
            report['reads_used'] += 1
        if error:
            return {'status':error,'target_resolution':resolution}
        if name == 'memory_delete':
            normalized = deepcopy(call)
            normalized['arguments']['memory_id'] = target['id']
            result = super()._apply(normalized,window_id,round_index,report)
            return {**result,'target_resolution':resolution}
        active = self._active_records()
        active['STATUS'] = NS(content=self.memory.status,category='status')
        try:
            return self.history.read(target,active,requested_view=args.get('view'),cursor=args.get('cursor'),
                                     handle=token if is_history else None)
        except HistoryError as exc:
            return {'status':exc.status,'requested_view':args.get('view','auto'),'resolved_view':None,
                    'complete':False,'page_sequence_complete':False,'next_cursor':None}

    def _stop_batch_after(self, call, result):
        return result['status'] in {
            'unknown_tool','invalid_tool_arguments','invalid_source_ids','invalid_cursor',
            'source_not_displayed','tool_error','entry_not_found','source_changed',
            'ambiguous_memory_id','invalid_delete_target','memory_target_changed',
            'invalid_history_handle','historical_read_only'}
