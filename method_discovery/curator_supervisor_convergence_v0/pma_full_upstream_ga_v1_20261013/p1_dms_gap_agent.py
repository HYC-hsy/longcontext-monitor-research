"""Independent raw-material selector with a generated unresolved-item index."""
from copy import deepcopy
import json
from types import SimpleNamespace as NS
from p1_context_history import InputMemoryHistory, HistoryError, PREFIX
from p1_linked_agent import READ_LIMIT, CONTINUATION_LIMIT
from p1_source_archive import encode
from p1_dms_agent import DMSP1Agent, DMSMaterialStore, SYSTEM as MATERIAL_SYSTEM

CANDIDATE = 'dms-gap-index-v1'
PENDING_MAX_CHARS = 240
SYSTEM = MATERIAL_SYSTEM.replace(
    'Select useful task requirements and complete visible events, and organize related\nmaterial into knowledge, procedural or gap groups. Use only the three memory tools.\nDo not write summaries, titles, success labels, plans or a new completion status.',
    'Maintain useful task requirements and complete visible events incrementally.\nKeep still-useful old entries; change them only when new material calls for it.\nUse only the three memory tools. Knowledge and procedural groups contain selected\noriginal material, without generated summaries, titles or success labels. Do not\nwrite a new completion status.').replace(
    'A gap means you selected material for later confirmation, not proven failure.\nSelect the smallest useful groups without dropping necessary related material.',
    'A gap is a task-relevant condition still to satisfy or a question still to answer.\nFor a gap only, write one short pending sentence and select its related material.\nThis generated unresolved index is not a fact, failure log, cause guess or plan.\nClose only the same unresolved item: observing failure or clearing a prerequisite\ndoes not satisfy the remaining goal. Keep factual experiences as original material.\nWhen new observations limit an older explanation, group the related material\ntogether rather than keeping an unverified explanation as an isolated known fact.\nSelect the smallest useful groups without dropping necessary related material.')
SYSTEM += ('\nReading a group also gives a directory of records behind its generation input, '
           'not supporting evidence. Returned H1 handles may be read or cited in source_ids, '
           'but never deleted. They inherit frozen material, not verified facts. Read only when useful.\n')


def frozen_pending(row):
    if (not row or row['category']!='gap' or not row.get('ref')
            or row['ref'].get('association')=='typed_legacy_not_verified'):
        return None
    try:
        value=json.loads(row['content'])
    except (ValueError,TypeError):
        return None
    if (isinstance(value,dict) and value.get('index_kind')=='generated_unresolved_index_not_fact'
            and isinstance(value.get('pending'),str)):
        return value
    return None


def cited_handles(source_ids, aliases):
    cited=[]
    for token in source_ids:
        item=aliases.get(token) if isinstance(token,str) else None
        if item is None or item['kind']!='memory':continue
        if token.startswith(PREFIX) and item.get('historical_row') is not None:cited.append(token)
        cited.extend(item['ref'].get('cited_history_handles',[]))
    return list(dict.fromkeys(cited))


class GapIndexMaterialStore(DMSMaterialStore):
    candidate_name = CANDIDATE

    def resolve(self, source_ids, aliases):
        resolved=super().resolve(source_ids,aliases)
        pending=[]
        for token in source_ids:
            item=aliases[token]
            if item['kind']!='memory':continue
            ref=item['ref']
            pending.extend(deepcopy(ref.get('inherited_pending_indices',[])))
            group=frozen_pending(item.get('historical_row') or item.get('frozen_record'))
            if group:
                pending.append({'memory_id':item['id'],'kind':'generated_unresolved_index_not_fact',
                                'pending':group['pending']})
            row=item.get('historical_row')
            if row is not None and not ref['sources']:
                resolved['inherited_unassociated'].append(row['memory_id'])
        unique={}
        for value in pending:unique.setdefault((value['memory_id'],value['pending']),value)
        if unique:resolved['inherited_pending_indices']=list(unique.values())
        cited=cited_handles(source_ids,aliases)
        if cited:resolved['cited_history_handles']=cited
        resolved['inherited_unassociated']=list(dict.fromkeys(resolved['inherited_unassociated']))
        return resolved

    def _read_fields(self, target, sources):
        fields = super()._read_fields(target, sources)
        # Persisted JSON sorts object keys; keep page order stable before/after reopening.
        order = {s['source_id']:i for i,s in enumerate(sources)}
        fields.sort(key=lambda row:(order[row[0]], row[1]!='directory', row[1]))
        historical=target.get('historical_record')
        group = frozen_pending(historical) if historical else self.state['groups'].get(target.get('id'))
        if group and (historical or group['category'] == 'gap'):
            fields.insert(0, (target['id'], 'generated_unresolved_index_not_fact',
                              'raw_string', group['pending']))
        ref=target.get('ref') or self.state['refs'].get(target.get('id')) or {}
        for i,value in enumerate(ref.get('inherited_pending_indices',[])):
            fields.insert(i,('inherited_pending_'+str(i),'inherited_generated_unresolved_index_not_fact',
                             'json_value',encode(value)))
        return fields


class GapIndexP1Agent(DMSP1Agent):
    maintenance_system = SYSTEM
    input_tail = ('\nKeep useful original materials with the three tools. No new status or factual conclusions; '
                  'only gap may add a short pending index.\n')
    store_type = GapIndexMaterialStore

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history = InputMemoryHistory(self.links,self.source_archive)
        # Make a historical entry reachable even when selected raw sources are long.
        self.history.directory_first = True
        self.history.citations_as_sources = True

    def _input(self, observation, step, raw_events):
        result = super()._input(observation,step,raw_events)
        active = self._active_records()
        self._input_history_records=[]
        for item in self.frozen_aliases.values():
            if item['kind']=='memory':
                item['frozen_record']=self.history.record(item['id'],active[item['id']].category,
                    active[item['id']].content,item['ref'])
                self._input_history_records.append(item['frozen_record'])
        status = self.frozen_aliases['STATUS']
        if self.memory.status or status['ref']:
            self._input_history_records.append(self.history.record('STATUS','status',self.memory.status,status['ref']))
        return result

    def _capture_window(self, *args, **kwargs):
        kwargs['input_memory_coverage'] = self.history.coverage(
            self._input_history_records,kwargs.get('presented_source_receipts',()))
        return super()._capture_window(*args,**kwargs)

    def _history_collision(self, token):
        return token in self.request_aliases or any(item.get('id')==token
            for item in self.request_aliases.values() if item['kind']=='memory')

    def _apply(self, call, window_id, round_index, report):
        name,args = call['name'],call['arguments']
        if name=='memory_keep' and isinstance(args,dict) and isinstance(args.get('source_ids'),list):
            original=self.request_aliases
            try:
                extended=deepcopy(original)
                for token in args['source_ids']:
                    if isinstance(token,str) and token.startswith(PREFIX):
                        if self._history_collision(token):return {'status':'invalid_source_ids'}
                        row=self.history.load(token)
                        ref=row['ref'] or {'sources':[],'inherited_unassociated':[row['memory_id']]}
                        extended[token]={'kind':'memory','id':row['memory_id'],'ref':ref,'historical_row':row}
                for handle in cited_handles(args['source_ids'],extended):
                    self.history.load(handle)
                self.request_aliases=extended
                return super()._apply(call,window_id,round_index,report)
            except HistoryError as exc:
                return {'status':'invalid_source_ids' if exc.status=='invalid_history_handle' else 'source_binding_error'}
            finally:
                self.request_aliases=original
        if name=='memory_delete' and isinstance(args,dict) and isinstance(args.get('memory_id'),str):
            token=args['memory_id']
            if token.startswith(PREFIX):
                return {'status':'historical_read_only' if not self._history_collision(token) else 'tool_error',
                        'error':'historical_read_only_or_ambiguous_target'}
        if (name!='memory_read_source' or not isinstance(args,dict) or set(args)-{'memory_id','cursor'}
                or not isinstance(args.get('memory_id'),str) or round_index>=CONTINUATION_LIMIT
                or report['reads_used']>=READ_LIMIT):
            return super()._apply(call,window_id,round_index,report)
        token=args['memory_id'];historical=token.startswith(PREFIX)
        report['read_requests']+=1;report['reads_used']+=1
        if historical:
            if self._history_collision(token):
                return {'status':'tool_error','error':'ambiguous_history_handle'}
            target=None;audit={}
        else:
            target,audit=self._resolve_displayed_target(token)
            if target is None:return audit
        active=self._active_records()
        active['STATUS']=NS(content=self.memory.status,category='status')
        try:
            return self.history.read(target,active,cursor=args.get('cursor'),
                    handle=token if historical else None,
                    read_metadata={'resolved_memory_id':audit['resolved_memory_id']} if audit else None)
        except HistoryError as exc:
            return {'status':exc.status,'complete':False,'page_sequence_complete':False,'next_cursor':None}

    def _stop_batch_after(self, call, result):
        return result['status'] in {'invalid_history_handle','historical_read_only',
            'context_missing','source_changed','entry_not_found'}

    def get_tools_schema(self):
        tools = deepcopy(super().get_tools_schema())
        keep = tools[0]['function']
        keep['description'] = ('Keep selected original materials. For gap only, add one short '
                               'pending condition or question; it is a generated unresolved index, not a fact or plan. '
                               'Returned H1 handles may be cited to inherit frozen material.')
        keep['parameters']['properties']['pending'] = {
            'type': 'string', 'minLength': 1, 'maxLength': PENDING_MAX_CHARS,
            'description': 'Required only for gap: one short unresolved condition or question. Forbidden for other categories.'}
        tools[-1]['function']['description'] += (' Group reads include a generation-input directory, not evidence. '
            'Returned H1 handles can be read or cited, never deleted; continue next_cursor unchanged.')
        return tools

    def _valid_keep(self, args):
        if (not isinstance(args, dict) or not isinstance(args.get('category'),str)
                or args['category'] not in {'knowledge','procedural','gap'}):
            return False
        if args['category'] != 'gap':
            return super()._valid_keep(args)
        text = args.get('pending')
        return (set(args) == {'category','source_ids','pending'} and isinstance(text,str)
                and bool(text.strip()) and len(text) <= PENDING_MAX_CHARS)

    def _group_metadata(self, args):
        group = super()._group_metadata(args)
        if args['category'] == 'gap':
            group.update(pending=args['pending'], index_kind='generated_unresolved_index_not_fact')
        cited=cited_handles(args['source_ids'],self.request_aliases)
        if cited:group['cited_history_handles']=cited
        return group

    def _group_label(self, key):
        group = self.links.state['groups'][key]
        label={}
        if group['category'] == 'gap':
            label['generated_unresolved_index']={'text':group['pending'],'kind':group['index_kind']}
        cited=self.links.state['refs'][key].get('cited_history_handles')
        if cited:label['history_citations_not_proof']=cited
        inherited=self.links.state['refs'][key].get('inherited_pending_indices')
        if inherited:label['inherited_unresolved_indices']=deepcopy(inherited)
        return label
