"""Input coverage in existing windows and issued, task-bound read capabilities."""
from copy import copy, deepcopy
import hashlib
import hmac
import json
from types import SimpleNamespace as NS
from p1_source_archive import digest, encode

PREFIX = 'H1.'


class HistoryError(ValueError):
    def __init__(self, status):
        self.status = status
        super().__init__(status)


class InputMemoryHistory:
    def __init__(self, links, archive):
        self.links, self.archive = links, archive

    def record(self, key, category, content, ref):
        result = {'memory_id':key,'category':category,'content':content,'ref':deepcopy(ref)}
        self._validate_record(result)
        return result

    def _validate_record(self, row):
        if (not isinstance(row,dict) or not isinstance(row.get('memory_id'),str) or
                not isinstance(row.get('category'),str) or not row['category'] or 'ref' not in row or
                not isinstance(row.get('content'),str)):
            raise HistoryError('source_binding_error')
        ref = row.get('ref')
        if ref is not None and (not isinstance(ref,dict) or
                ref.get('content_sha256') != digest(row['content']) or
                ref.get('category') != row['category']):
            raise HistoryError('source_binding_error')
        return row

    def coverage(self, records, receipts):
        handles = []
        for item in receipts:
            args = item.get('call',{}).get('arguments',{})
            value = args.get('memory_id') if isinstance(args,dict) else None
            if isinstance(value,str) and value.startswith(PREFIX) and value in self.links.state.get('history_grants',{}):
                self.load(value)
                if value not in handles:
                    handles.append(value)
        return {'schema':'input-memory-coverage-v1',
                'records':[self.record(r['memory_id'],r['category'],r['content'],r['ref']) for r in records],
                'read_handles':handles}

    def _window(self, window_id, sha):
        try:
            raw = self.archive.window_path(window_id).read_bytes().decode('utf-8')
            value = json.loads(raw)
            if (not sha or digest(raw) != sha or value['task_id'] != self.links.state['task_id'] or
                    self.archive.task_id != self.links.state['task_id'] or
                    self.archive.task != self.links.state['task'] or value['cycle_id'] != window_id or
                    not isinstance(value['model_input'],str)):
                raise ValueError('window identity')
        except FileNotFoundError:
            raise HistoryError('context_missing') from None
        except (OSError,ValueError,KeyError,TypeError):
            raise HistoryError('source_binding_error') from None
        return value

    def _handle(self, locator):
        payload = encode([self.links.state['task_id'],digest(self.links.state['task']),locator]).encode()
        return PREFIX + hmac.new(self.links.state['secret'].encode(),payload,hashlib.sha256).hexdigest()

    def load(self, handle):
        if not isinstance(handle,str) or not handle.startswith(PREFIX):
            raise HistoryError('invalid_history_handle')
        locator = self.links.state.get('history_grants',{}).get(handle)
        if locator is None or not isinstance(locator,dict) or not hmac.compare_digest(handle,self._handle(locator)):
            raise HistoryError('invalid_history_handle')
        try:
            window = self._window(locator['window_id'],locator['window_sha256'])
            index = locator['index']
            if type(index) is not int or index < 0:
                raise ValueError('index')
            row = window['input_memory_coverage']['records'][index]
            if digest(encode(row)) != locator['record_sha256']:
                raise ValueError('snapshot')
            return deepcopy(self._validate_record(row))
        except (KeyError,TypeError,IndexError,ValueError) as exc:
            if isinstance(exc,HistoryError):
                raise
            raise HistoryError('source_binding_error') from None

    def _directory(self, ref):
        if not ref or not ref.get('context_window'):
            return [], {}, 'unrecorded'
        window = self._window(ref['context_window'],ref.get('context_sha256'))
        coverage = window.get('input_memory_coverage')
        if coverage is None:
            return [], {}, 'unrecorded'
        if (not isinstance(coverage,dict) or coverage.get('schema') != 'input-memory-coverage-v1' or
                not isinstance(coverage.get('records'),list) or not isinstance(coverage.get('read_handles'),list)):
            raise HistoryError('source_binding_error')
        rows, pending = [], {}
        for index, row in enumerate(coverage['records']):
            self._validate_record(row)
            locator = {'window_id':ref['context_window'],'window_sha256':ref['context_sha256'],
                       'index':index,'record_sha256':digest(encode(row))}
            handle = self._handle(locator)
            pending[handle] = locator
            rows.append((handle,row,'displayed_record'))
        for handle in coverage['read_handles']:
            if not isinstance(handle,str):
                raise HistoryError('source_binding_error')
            rows.append((handle,self.load(handle),'earlier_read_handle'))
        fields = []
        for index,(handle,row,visibility) in enumerate(rows):
            data = {'history_handle':handle,'memory_id':row['memory_id'],'category':row['category'],
                    'content_preview':row['content'][:60],'content_preview_truncated':len(row['content'])>60,
                    'association':(row['ref'] or {}).get('association','legacy_unrecorded'),
                    'visibility':visibility,'original_read_not_implied':True}
            fields.append(('input_memory_'+str(index),'input_memory','json_value',encode(data)))
        return fields, pending, 'recorded'

    def read(self, target, active, *, requested_view=None, cursor=None, handle=None, read_metadata=None):
        if requested_view not in (None,'sources','context'):
            raise HistoryError('invalid_tool_arguments')
        reader = self.links
        historical = None
        if handle is not None:
            historical = self.load(handle)
            # Only this frozen record is substituted; event data, task and signing key are shared.
            reader = copy(self.links)
            reader.state = {**self.links.state,'refs':{handle:historical['ref']}}
            target = {'kind':'memory','id':handle,'ref':historical['ref'],
                      'historical_memory_id':historical['memory_id'],'historical_record':historical}
            active = {handle:NS(content=historical['content'],category=historical['category'])}
        key = target.get('id',target.get('source_id'))
        ref = reader.state['refs'].get(key) if target['kind'] in ('memory','status') else None
        if historical is None and target['kind'] in ('memory','status'):
            row = active.get(key)
            if row is None:
                return {'status':'entry_not_found'}
            if 'ref' in target and target['ref'] != ref:
                return {'status':'source_changed'}
            if ref and (ref['content_sha256'] != digest(row.content) or ref['category'] != row.category):
                raise HistoryError('source_binding_error')
        directory, pending, coverage_status = self._directory(ref)
        sources = (ref or {}).get('sources',[]) if target['kind'] in ('memory','status') else [target]
        resolved = requested_view or ('context' if not sources and ref and ref.get('context_window') else 'sources')
        metadata = {'requested_view':requested_view or 'auto','resolved_view':resolved,
                    'fallback_reason':'no_linked_sources' if requested_view is None and resolved=='context' else None,
                    'input_memory_count':len(directory),'input_memory_coverage':coverage_status,
                    'input_memory_scope':'Generation input coverage, not claim support; history handles are read-only.'}
        if read_metadata is not None:
            metadata.update(read_metadata)
        fields = list(directory)
        if historical is not None:
            metadata.update(historical=True,historical_memory_id=historical['memory_id'])
            fields.append(('history','derived_memory_content','raw_string',historical['content']))
        result = reader.read(target,active,view=resolved,cursor=cursor,archive=self.archive,
            _extra_fields=fields,_read_metadata=metadata,
            _atomic_fields={(sid,field) for sid,field,_,_ in directory}, _extra_first=getattr(self,'directory_first',False) or resolved=='context')
        if 'requested_view' not in result:
            result.update(metadata)
        for name,value in (('complete',False),('page_sequence_complete',False),
                           ('semantic_verification_performed',False),('next_cursor',None)):
            result.setdefault(name,value)
        issued = {}
        for part in result.get('parts',[]):
            if part['field']=='input_memory' and part['start']==0 and part['end']==part['total']:
                token = json.loads(part['text'])['history_handle']
                if token in pending:
                    issued[token] = pending[token]
        if issued:
            state = deepcopy(self.links.state)
            grants = state.setdefault('history_grants',{})
            if any(token in grants and grants[token] != locator for token,locator in issued.items()):
                raise HistoryError('source_binding_error')
            if any(token not in grants for token in issued):
                grants.update(issued)
                self.links.commit(state)
        return result
