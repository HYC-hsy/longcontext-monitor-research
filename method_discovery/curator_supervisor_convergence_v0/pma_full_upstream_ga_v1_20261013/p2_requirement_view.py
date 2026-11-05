"""Frozen full-bank P2 browse/source capabilities; no persistent state writes."""
from copy import copy, deepcopy
import json
from types import SimpleNamespace as NS
import uuid
from p1_source_archive import encode, digest
from p1_source_links import SourceLinks
from p1_context_history import HistoryError, InputMemoryHistory
from p1_requirements import RequirementHistory, KEY, canonical, catalog, assignment, topics
from tag_selection_contract import Snapshot, Item


def p1_boundary_error(p1, *, allow_uninitialized=False):
    if p1._active or p1._requirement_active:
        return 'p1_maintenance_active'
    try:
        saved = json.loads(p1.links.path.read_bytes())
        state = saved['data']
        if saved['sha256']!=digest(encode(state)):
            return 'p1_state_unavailable_or_corrupt'
        if saved['sha256']!=digest(encode(p1.links.state)):
            return 'p1_state_not_reconciled'
        if (state.get('schema')!='p1-source-links-v1' or
                any(not isinstance(state.get(key),dict) for key in ('events','accepted','refs','bank',KEY)) or
                not isinstance(state.get('history_grants',{}),dict) or
                not isinstance(state.get('presented'),list) or
                not isinstance(state.get('secret'),str) or not state['secret']):
            return 'p1_state_unavailable_or_corrupt'
        if encode(state['bank'])!=encode(p1.memory.to_dict()):
            return 'p1_live_bank_not_committed'
        if not isinstance(state['refs'],dict) or not isinstance(state['bank']['status'],str):
            return 'p1_state_unavailable_or_corrupt'
        status_ref = state['refs'].get('STATUS')
        if status_ref is None and state['bank']['status']:
            return 'p1_state_unavailable_or_corrupt'
        if status_ref is not None and (status_ref['category']!='status' or
                status_ref['content_sha256']!=digest(state['bank']['status'])):
            return 'p1_state_unavailable_or_corrupt'
        metadata = state[KEY]
        fixed = metadata['catalog']
        if (metadata['schema']!=KEY or metadata['task_sha256']!=digest(p1.task)
                or state['task']!=p1.task or state['task_id']!=p1.source_archive.task_id):
            return 'p1_state_unavailable_or_corrupt'
        if fixed is None:
            if not allow_uninitialized:
                return 'p1_requirements_uninitialized'
            if state['refs'] or any(state['bank'][k] for k in ('knowledge','procedural','gaps','status')):
                return 'p1_state_unavailable_or_corrupt'
        elif catalog(fixed)!=fixed:
            return 'p1_state_unavailable_or_corrupt'
        for key,row in p1._active_records().items():
            ref = state['refs'][key]
            if (ref['category']!=row.category or ref['content_sha256']!=digest(row.content)
                    or assignment(ref['requirements'],fixed or [])!=ref['requirements']):
                return 'p1_state_unavailable_or_corrupt'
        cycles = metadata['cycles']
        if not isinstance(cycles,dict) or any(not isinstance(row,dict) or
                row.get('phase') not in ('done','abandoned') for row in cycles.values()):
            return 'unresolved_p1_maintenance_cycle'
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return 'p1_state_unavailable_or_corrupt'
    return None


def validate_continuation(p1, report, *, allow_uninitialized=False):
    """Ordinary memory errors may continue only from a currently healthy P1 state."""
    if report.get('error_policy')!='continue_without_reminder':
        return
    try:
        error = p1_boundary_error(p1,allow_uninitialized=allow_uninitialized)
    except Exception as exc:
        error = 'p1_state_validation_failed'
        report['validation_error_type'] = type(exc).__name__
    if error:
        report.update(optional_memory_status=report['status'],status='engineering_error',
            failure_kind='integrity',error_stage='continuation_validation',error=error,
            should_inject=False,context_for_action=None,delivery=None)
        report.pop('error_policy',None)


class SnapshotLinks(SourceLinks):
    def commit(self, state):
        # Grants belong to this selection invocation, never the P1 bundle.
        self.state = deepcopy(state)

    def read(self, *args, **kwargs):
        reader = copy(self)
        reader.state = {**self.state,'secret':self.cursor_secret}
        return SourceLinks.read(reader,*args,**kwargs)


class SnapshotHistory(RequirementHistory):
    def __init__(self, links, archive, nonce):
        super().__init__(links,archive)
        self.prefix = 'P2H.'+nonce+'.'

    def load(self, handle):
        if handle.startswith(self.prefix):
            locator = self.links.state.get('history_grants',{}).get(handle)
            if locator is None:
                raise HistoryError('invalid_history_handle')
            raw = handle[len(self.prefix):]
            reader = copy(self)
            reader.links = copy(self.links)
            reader.links.state = {**self.links.state,'history_grants':{raw:locator}}
            return InputMemoryHistory.load(reader,raw)
        # Internal P1 citations remain verifiable, but the public endpoint never accepts them.
        return super().load(handle)

    def _directory(self, ref):
        fields,pending,status = super()._directory(ref)
        result, grants = [], {}
        for sid,field,encoding,text in fields:
            row = json.loads(text)
            raw = row['history_handle']
            handle = self.prefix+raw
            locator = pending.get(raw,self.links.state.get('history_grants',{}).get(raw))
            if locator is None:
                raise HistoryError('source_binding_error')
            row['history_handle'] = handle
            result.append((sid,field,encoding,encode(row)))
            grants[handle] = locator
        return result,grants,status


class RequirementSelectionView:
    def __init__(self, p1):
        error = p1_boundary_error(p1)
        if error:
            raise RuntimeError(error)
        live_state = p1.links.state
        if live_state['bank']!=p1.memory.to_dict() or live_state['task']!=p1.task or live_state[KEY]['catalog'] is None:
            raise ValueError('uncommitted or uninitialized task snapshot')
        state = {key:deepcopy(live_state.get(key,{})) for key in
                 ('task_id','task','secret','events','refs','bank','history_grants')}
        self.id = uuid.uuid4().hex
        self.catalog = tuple(live_state[KEY]['catalog'])
        self.task_id, self.task = state['task_id'],state['task']
        self.items = tuple(Item(r.id,'',r.category,r.content) for r in
            p1.requirement_state.ordered(p1._active_records().values()))
        self.snapshot = Snapshot(self.id,'selection_'+self.id,'task_sha256_'+digest(self.task),self.task,self.items)
        self.aliases = {f'M{i}':row for i,row in enumerate(self.items,1)}
        self.attributes = {f'M{i}':deepcopy(p1.requirement_state.attributes(p1._active_records()[row.id]))
                           for i,row in enumerate(self.items,1)}
        self.links = SnapshotLinks.__new__(SnapshotLinks)
        self.links.root,self.links.path = p1.links.root,p1.links.path
        self.links.state = state
        self.links.cursor_secret = uuid.uuid4().hex
        self.history = SnapshotHistory(self.links,copy(p1.source_archive),self.id)
        self.seen = {'TASK'}
        self._coverage = {}

    def record(self, alias):
        row = self.aliases[alias]
        ref = self.links.state['refs'][row.id]
        attributes = deepcopy(self.attributes[alias])
        if not attributes['requirements']:
            attributes.pop('requirements')
        return {'alias':alias,'memory_id':row.id,'category':row.category,'content':row.content,
                **attributes,'source_association':ref['association'],
                'source_count':len(ref['sources']),'sources_are_not_proof':True}

    def present(self, aliases):
        rows = [self.record(alias) for alias in aliases]
        self.seen.update(aliases)
        return rows

    def initial_records(self, aliases):
        rows = []
        for alias in aliases:
            row,attributes = self.aliases[alias],self.attributes[alias]
            ref = self.links.state['refs'][row.id]
            order = attributes['source_event_order']
            rows.append({'alias':alias,'memory_id':row.id,'category':row.category,'content':row.content,
                **({'requirements':deepcopy(attributes['requirements'])} if attributes['requirements'] else {}),
                'source':{'association':ref['association'],'count':len(ref['sources']),
                          'accepted_event_range':[order['first'],order['last']]}})
        self.seen.update(aliases)
        return rows

    def groups(self, aliases):
        return {'requirements':[{'requirement':text,'aliases':[a for a in aliases if text in
                    self.attributes[a]['requirements']]} for text in topics(self.catalog)],
                'unclassified_aliases':[a for a in aliases if not self.attributes[a]['requirements']]}

    def browse(self, *, view='all', requirement=None, category=None, cursor=None, model_view=False):
        if (view not in ('all','requirement') or (view!='requirement' and requirement is not None) or
                category not in (None,'knowledge','procedural','gap')):
            return {'status':'invalid_tool_arguments'}
        if view=='requirement':
            if requirement is None:
                return {'status':'invalid_tool_arguments'}
            try:
                requirement = canonical(requirement)
            except ValueError:
                return {'status':'unknown_requirement'}
            if requirement not in topics(self.catalog):
                return {'status':'unknown_requirement'}
        aliases = [a for a in self.aliases if view=='all' or
            (view=='requirement' and requirement in self.attributes[a]['requirements'])]
        aliases = [a for a in aliases if category is None or self.aliases[a].category==category]
        records = {a:self.record(a) for a in aliases}
        if model_view:
            for record in records.values():record.pop('memory_id',None)
        fields = [(a,'record','json_value',encode(records[a])) for a in aliases]
        metadata = {'snapshot_id':self.id,'browse_view':view,'requirement':requirement,'category':category,
            'scope':'all frozen active records matching this filter; not only the initial BM25 subset',
            'matching_record_count':len(aliases),'all_active_record_count':len(self.items),
            'matching_category_counts':{c:sum(self.aliases[a].category==c for a in aliases)
                                        for c in ('knowledge','procedural','gap')},
            'gap_scope':'Active GAP records describe recorded needs, not verified completion.',
            'record_scope':'Records may span pages; join record parts and JSON-decode. Partial records are incomplete.'}
        result = self.links.read({'kind':'status','id':'P2_BROWSE_'+self.id,'ref':None},
            {'P2_BROWSE_'+self.id:NS(content='',category='status')},view='sources',cursor=cursor,
            _extra_fields=fields,_read_metadata=metadata)
        for part in result.get('parts',[]):
            alias = part['source_id']
            ranges = self._coverage.setdefault((alias,model_view),[])
            ranges.append((part['start'],part['end']))
            end = 0
            for start,stop in sorted(ranges):
                if start>end:
                    break
                end = max(end,stop)
            if end==part['total']:
                self.seen.add(alias)
        if result.get('status')!='invalid_cursor':
            result['status'] = 'browse_complete' if result['page_sequence_complete'] else 'browse_partial'
        return result

    def read_source(self, *, memory_id, view=None, cursor=None, alias_only=False):
        if not isinstance(memory_id,str):
            return {'status':'invalid_tool_arguments'}
        matches = {a for a,row in self.aliases.items() if a==memory_id or (not alias_only and row.id==memory_id)}
        special = memory_id in ('TASK','STATUS') or memory_id.startswith(self.history.prefix)
        if len(matches)+bool(special)>1:
            return {'status':'ambiguous_memory_id'}
        active = {row.id:row for row in self.items}
        active['STATUS'] = NS(content=self.links.state['bank']['status'],category='status')
        try:
            if memory_id.startswith(self.history.prefix):
                return self.history.read(None,{},requested_view=view,cursor=cursor,handle=memory_id)
            if matches:
                alias = next(iter(matches))
                if alias not in self.seen:
                    return {'status':'record_not_yet_shown'}
                key = self.aliases[alias].id
                target = {'kind':'memory','id':key,'ref':self.links.state['refs'][key]}
            elif memory_id=='STATUS':
                target = {'kind':'status','id':'STATUS','ref':self.links.state['refs'].get('STATUS')}
            elif memory_id=='TASK':
                target = {'kind':'task','source_id':'TASK'}
            else:
                return {'status':'source_not_in_snapshot_scope'}
            return self.history.read(target,active,requested_view=view,cursor=cursor)
        except HistoryError as exc:
            return {'status':exc.status,'complete':False,'page_sequence_complete':False,'next_cursor':None}

    def selection_valid(self, p1, selected):
        self.validation_error = p1_boundary_error(p1)
        if self.validation_error:
            return False
        if p1.task!=self.task or p1.links.state['task_id']!=self.task_id:
            return False
        current = p1._active_records()
        for alias in selected:
            if alias=='TASK':
                continue
            row = self.aliases[alias]
            live = current.get(row.id)
            if (live is None or live.category!=row.category or live.content!=row.content or
                    p1.links.state['refs'].get(row.id)!=self.links.state['refs'][row.id]):
                return False
        return True

