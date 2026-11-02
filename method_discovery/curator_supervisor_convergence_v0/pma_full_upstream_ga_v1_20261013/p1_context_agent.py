"""Opt-in generation-context consumer; no changes to memory write policy."""
from copy import deepcopy
from p1_source_archive import digest, encode
from p1_linked_agent import LinkedSourceP1Agent, SYSTEM as LINKED_SYSTEM, READ_LIMIT, CONTINUATION_LIMIT

SYSTEM = LINKED_SYSTEM + ("\nWhen selected sources are insufficient to understand an entry, memory_read_source "
    "with view='context' can page its frozen visible generation input. Default view='sources' "
    "returns selected sources. Context is not per-claim evidence; read only when useful.\n")


class ContextSourceP1Agent(LinkedSourceP1Agent):
    system = SYSTEM
    context_views = True
    memory_source_label = 'memory IDs or M aliases for reading/deletion'

    def get_tools_schema(self):
        tools = super().get_tools_schema()
        delete = next(t['function'] for t in tools if t['function']['name']=='memory_delete')
        delete['description'] += ' Accepts a frozen displayed M alias or an original memory ID; never E/TASK/STATUS.'
        tool = tools[-1]['function']
        tool['description'] += ' Frozen M aliases and displayed memory IDs resolve identically; ambiguity is rejected. Optional context view reads a memory/STATUS frozen generation input, not proof.'
        tool['parameters']['properties']['view'] = {
            'type':'string', 'enum':['sources','context'], 'default':'sources'}
        return tools

    def _input(self, observation, step, raw_events):
        prompt, marked, projection, visible = super()._input(observation, step, raw_events)
        self._context_records = {key: {
            'content_sha256':digest(row.content), 'category':row.category,
            'ref':deepcopy(self.links.state['refs'].get(key))}
            for key,row in self._active_records().items()}
        return prompt, marked, projection, visible

    def _resolve_target(self, value, *, deleting):
        candidates = []
        if value in self.request_aliases:
            candidates.append(self.request_aliases[value])
        candidates.extend(t for t in self.request_aliases.values()
                          if t.get('kind') == 'memory' and t.get('id') == value)
        frozen = self._context_records
        if value in frozen and (deleting or candidates):
            candidates.append({'kind':'memory','id':value,'ref':frozen[value]['ref']})
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

    def _apply(self, call, window_id, round_index, report):
        name, args = call['name'], call['arguments']
        if name not in {'memory_read_source','memory_delete'}:
            return super()._apply(call,window_id,round_index,report)
        # Reads retain the inherited argument validation and shared budget accounting.
        allowed = {'memory_id'} if name == 'memory_delete' else {'memory_id','view','cursor'}
        if (not isinstance(args,dict) or set(args)-allowed or
                not isinstance(args.get('memory_id'),str) or
                (name == 'memory_read_source' and args.get('view','sources') not in ('sources','context'))):
            return super()._apply(call,window_id,round_index,report)
        if name == 'memory_read_source' and (round_index >= CONTINUATION_LIMIT or report['reads_used'] >= READ_LIMIT):
            return super()._apply(call,window_id,round_index,report)
        target, resolution = self._resolve_target(args['memory_id'],deleting=name == 'memory_delete')
        if target is None:
            if name == 'memory_read_source':
                report['read_requests'] += 1
                report['reads_used'] += 1
            return {'status':resolution['status'],'target_resolution':resolution}
        normalized = deepcopy(call)
        if target['kind'] == 'memory':
            normalized['arguments']['memory_id'] = target['id']
        result = super()._apply(normalized,window_id,round_index,report)
        return result if name == 'memory_read_source' else {**result, 'target_resolution':resolution}

    def _stop_batch_after(self, call, result):
        return result['status'] in {
            'unknown_tool','invalid_tool_arguments','invalid_source_ids','invalid_cursor',
            'source_not_displayed','tool_error','entry_not_found','source_changed',
            'ambiguous_memory_id','invalid_delete_target','memory_target_changed'}
