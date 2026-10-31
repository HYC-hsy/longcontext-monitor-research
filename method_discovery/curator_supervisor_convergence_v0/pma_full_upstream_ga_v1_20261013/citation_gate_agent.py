"""Opt-in prepublication gate, with zero/one author repair and final control receipts."""
from copy import deepcopy
import json
import asyncio
from contextvars import ContextVar
from pathlib import Path

from latest_evidence_gap_agent import LatestEvidenceGapMemoryAgent, latest_phase1_system
from evidence_gap_agent import WRITERS
from memory_agent.memory.memory_agent import MemoryOperation
from pma_evidence_review.live_citations import build_live, assess, visible_snapshot
from pma_evidence_review.prompt_strategy import ONE_SENTENCE
from pma_evidence_review.claim_split import STRATEGY as CLAIM_SPLIT
from pma_evidence_review import claim_split_simple as simple_split
from pma_evidence_review import claim_split_semantic as semantic_split
from pma_evidence_review import execution_link
from gap_evidence_alignment import _validate_catalog

SPLIT_STRATEGIES = (CLAIM_SPLIT, simple_split.STRATEGY, semantic_split.STRATEGY)
from pma_evidence_review.gate_control import repair, receipt
from pma_evidence_review.citation_inputs import identity
from pma_evidence_review.transport import CapturedTransport, durable
from pma_evidence_review.private_faults import record_failure


class CitationGateMemoryAgent(LatestEvidenceGapMemoryAgent):
    @property
    def transport_phase(self):
        return self._transport_phase.get()

    @transport_phase.setter
    def transport_phase(self, value):
        if not hasattr(self, '_transport_phase'):
            self._transport_phase = ContextVar('citation_transport_phase', default='maintenance')
        self._transport_phase.set(value)

    def __init__(self, *, review_directory=None, run_id='live', repair_limit=0,
                 review_strategy=ONE_SENTENCE, **kwargs):
        if review_strategy not in (ONE_SENTENCE, *SPLIT_STRATEGIES):raise ValueError('review_strategy')
        self.review_strategy=review_strategy
        if type(repair_limit) is not int or repair_limit not in (0,1):raise ValueError('repair_limit')
        super().__init__(**kwargs)
        self._tools=deepcopy(self._tools)
        for tool in self._tools:
            function=tool['function']
            if function['name'] in WRITERS:
                function['description']='Propose a memory write; only the host commit receipt confirms publication. '+function['description']
            elif function['name']=='memory_delete':
                if review_strategy == semantic_split.STRATEGY:
                    function['description']='Propose deletion of an existing gap only. Give a reason and literal visible citations; only the host receipt confirms deletion.'
                    properties=function['parameters']['properties']
                    properties['reason']={'type':'string','minLength':1}
                    properties['evidence']={'type':'array','minItems':1,'items':{'type':'object',
                        'properties':{'quote':{'type':'string','minLength':1},
                                      'source':{'type':'string','minLength':1}},
                        'required':['quote'],'additionalProperties':False}}
                    function['parameters']['required']=['memory_id','reason','evidence']
                else:
                    function['description']='Deletion is deferred in this mode: this tool has no citation protocol and will not delete an entry.'
        self.run_id,self.repair_limit=run_id,repair_limit
        self.review_directory=Path(review_directory) if review_directory is not None else None
        if self.review_directory is not None:self.review_directory.mkdir(parents=True,exist_ok=False)
        self.review_transport=CapturedTransport(self.llm,self.review_directory)
        self._review_result=None
        self.last_citation_gate_report={}
        self.pending_receipt=None
        self.receipt_deliveries=[]
        self._included_receipt=None
        self._execution_context=None

    def _maintenance_control_suffix(self):
        self._included_receipt=deepcopy(self.pending_receipt)
        if self._included_receipt is None:return ''
        return '\nHOST COMMIT RECEIPT — CONTROL ONLY (not a source; proposals are not commits):\n'+json.dumps(self._included_receipt,ensure_ascii=False)+'\n'

    async def process(self, observation, step_count=0):
        if self._active:raise RuntimeError('one serial gate cycle per agent is required')
        try:
            return await super().process(observation,step_count)
        finally:
            self._review_result=None
            self._draft=None
            self._parts=None
            self._included_receipt=None
            self._execution_context=None

    async def _call_llm_phase1(self, user_prompt):
        self.transport_phase='maintenance'
        self.last_citation_gate_report={'schema':'pma-live-citation-gate-v1','strategy':self.review_strategy,
            'repair_limit':self.repair_limit,'operations':[],'incomplete':False}
        if self._parts is None or self._parts.text!=user_prompt:
            self.last_citation_gate_report.update(incomplete=True,error_code='maintenance_context_invalid',
                final_receipt=deepcopy(self.pending_receipt),
                receipt_delivery='pending_delivery' if self.pending_receipt else 'none',
                prior_receipt_deliveries=deepcopy(self.receipt_deliveries))
            raise ValueError('gate_requires_valid_frozen_maintenance')
        system=latest_phase1_system().replace(
            'Every valid save becomes the latest content regardless of binding.',
            'A save becomes latest only after exact submitted citations pass the host review gate.').replace(
            'Malformed evidence records binding error while valid content is still committed;',
            'Malformed evidence prevents publication;').replace('Use no extra review phase.',
            'Host review is separate from your maintenance proposal.')
        # Identical initial author prompt in both modes: repair is a host opportunity.
        if self.review_strategy == semantic_split.STRATEGY:
            system+='\nHost gate: missing/non-exact citations are not publishable. A later host commit receipt states what actually changed.\n'
            system+='For every quote, copy one continuous literal span from visible material. Use separate evidence elements for separate spans; never concatenate snippets or insert ellipses. Keep relevant conditions and execution receipts, not just a success string in code. To delete an existing gap, provide its memory_id, a nonempty reason explaining why that specific gap is resolved, and evidence. Old gap text is the target, not proof of resolution. Other deletions remain deferred.\n'
        else:
            system+='\nHost gate: missing/non-exact citations are not publishable. Deletes are not executed because this tool has no citation protocol. A later host commit receipt states what actually changed.\n'
        kwargs={'prompt':user_prompt,'system':system}
        if self.use_structured_tools:kwargs['tools']=self.get_tools_schema()
        delivery=None
        if self._included_receipt is not None:
            delivery={'receipt_id':self._included_receipt['receipt_id'],
                'maintenance_request_sha256':self._parts.manifest.request_sha256,'status':'attempted'}
            self.receipt_deliveries.append(delivery)
        try:response=await self.llm.call(**kwargs)
        except BaseException:
            if delivery is not None:delivery['status']='delivery_uncertain_retry_same_id'
            self.last_citation_gate_report.update(incomplete=True,maintenance_failed=True,
                final_receipt=deepcopy(self.pending_receipt),prior_receipt_deliveries=deepcopy(self.receipt_deliveries))
            raise
        if delivery is not None:
            nonempty=bool(getattr(response,'tool_calls',None) or (getattr(response,'content',None) or '').strip())
            delivery['status']='response_received_consumed' if nonempty else 'empty_response_pending'
            if nonempty:self.pending_receipt=None
        self._maintenance_prompt=user_prompt
        operations=await self._execute_reviewed(response)
        self._review_result=(response,operations)
        return response

    def _execute_tool_calls(self,response):
        cached=self._review_result
        self._review_result=None
        if cached is None or cached[0] is not response:
            raise RuntimeError('review_response_not_available_or_already_consumed')
        return cached[1]

    def _valid_target(self,name,args):
        if name=='memory_delete' and self.review_strategy==semantic_split.STRATEGY:
            if not isinstance(args,dict) or set(args)!={'memory_id','reason','evidence'}:
                return False
            if not isinstance(args['reason'],str) or not args['reason'].strip() or not isinstance(args['evidence'],list) or not args['evidence']:
                return False
            try:return self.memory._content(args['memory_id'])[0]=='gap'
            except (ValueError,TypeError,KeyError):return False
        if name not in WRITERS or not isinstance(args,dict):return False
        allowed={'content','evidence'} | ({'memory_id'} if WRITERS[name]!='status' else set())
        if not set(args)<=allowed or not isinstance(args.get('content'),str) or not args['content'].strip():return False
        if 'memory_id' in args:
            key=args['memory_id']
            if not isinstance(key,str) or not key:return False
            try:return self.memory._content(key)[0]==WRITERS[name]
            except ValueError:return False
        return True

    def _dependency_target(self,name,args):
        """Only known host targets participate; malformed IDs identify nothing."""
        if not isinstance(args,dict):return None
        if name=='memory_update_status':return 'status'
        if name not in WRITERS and name!='memory_delete':return None
        key=args.get('memory_id')
        if not isinstance(key,str) or not key:return None
        try:category=self.memory._content(key)[0]
        except ValueError:return None
        if name=='memory_delete' or category==WRITERS[name]:return key
        return None

    async def _attempt(self,name,args,index,attempt,attempts):
        row={'attempt':attempt,'verdict':None,'engineering_status':'not_reviewed','success':False}
        attempts.append(row)
        if name=='memory_update_status' and len(args['content'])>self.memory._max_status_length:
            row.update(error_code='status_would_truncate',preparation='status_would_truncate')
            return row,None,None
        draft=self._operation_draft()
        base=self.memory.fork_write_draft()
        # Frozen pre-cycle legacy revisions may be materialized by an earlier commit.
        base.active_revisions = draft.active_revisions.copy()
        if name=='memory_delete' and self.review_strategy==semantic_split.STRATEGY:
            envelope,request=semantic_split.deletion_candidate(draft,self._parts,args,index,run_id=self.run_id)
            expected=envelope['operation']['target_revision_id']
            if draft.active_revisions.get(args['memory_id'])!=expected:
                raise ValueError('stale_delete_target')
            operation=self._apply_operation(draft,name,{'memory_id':args['memory_id']},index)
            operation.revision_id=expected
            operation.content=envelope['operation']['content']
        else:
            operation=self._apply_operation(draft,name,args,index)
            envelope,request=build_live(draft,self._parts,operation,index,run_id=self.run_id,review_strategy=self.review_strategy)
        if request is not None and self.review_strategy==semantic_split.STRATEGY:
            if self._execution_context is None:
                self._execution_context=execution_link.context_from_inventory(
                    self._parts.catalog, _validate_catalog,
                    getattr(self, '_accepted_execution_inventory', {}))
            request['audit_execution_context']=self._execution_context
            # Host-only action identity. A save_* tool may create OR revise;
            # the reviewer must not guess from the availability of old text.
            if name=='memory_delete':
                request['audit_operation_kind']='delete'
                request['audit_before_entry']={'content':envelope['operation']['existing_gap']}
            else:
                revision=draft.revisions[operation.revision_id]
                previous=revision.previous_revision_id
                request['audit_operation_kind']=('update' if name=='memory_update_status' or previous
                                                 else 'save')
                old=draft.revisions.get(previous) if previous else None
                old_text=draft.blobs.get(old.content_sha256) if old is not None else None
                request['audit_before_entry']=({'content':old_text} if isinstance(old_text,str)
                                               else None)
        operation.content_status='candidate_not_published'
        row['candidate']=deepcopy(vars(operation))
        report_request=(semantic_split.split_request_dto(request)
                        if request is not None else None)
        row.update(candidate=deepcopy(vars(operation)),input=envelope,request=report_request,
                   preparation=envelope['preparation']['status'])
        if request is None:row['error_code']='citation_preparation_'+row['preparation']
        else:
            self.transport_phase='citation_review'
            if self.review_strategy in (simple_split.STRATEGY,semantic_split.STRATEGY):
                split_module=(semantic_split if self.review_strategy==semantic_split.STRATEGY else simple_split)
                async with self._split_slot:
                    split = await split_module.split_stage(request, self.review_transport)
                async with self._review_slot:
                    result = await split_module.review_stage(request, self.review_transport, split)
                row.update(result)
            else:
                row.update(await assess(request,self.review_transport))
            if row['engineering_status']!='ok':row['error_code']='citation_'+row['engineering_status']
            elif row['verdict']!='supported':row['error_code']='citation_'+row['verdict']
        if self.review_strategy in (simple_split.STRATEGY,semantic_split.STRATEGY) and name!='memory_delete':
            self._staged_bases[id(draft)] = base
        return row,draft,operation

    def _rebase_candidate(self, draft, operation):
        """Merge one independently reviewed write, retaining its immutable identity.

        Never publish the speculative whole bank or regenerate an audited operation.
        History.add checks collisions; normal publication validates the merged delta.
        """
        base = self._staged_bases.pop(id(draft))
        if draft._draft_generation == self.memory._generation:
            return draft
        key = operation.memory_id
        if self.memory.active_revisions.get(key) != base.active_revisions.get(key):
            raise ValueError('stale_candidate_target')
        fresh = self.memory.fork_write_draft()
        for name in (*draft._HISTORIES, 'alignments', '_reserved_ids', '_retired_ids'):
            history = getattr(fresh, name)
            for identity, value in getattr(draft, name).delta(getattr(base, name)):
                history = history.add(identity, value)
            setattr(fresh, name, history)
        fresh.active_revisions[key] = draft.active_revisions[key]
        if key == 'status':
            fresh._status = draft._status
        else:
            kind = draft._content(key)[0]
            field = '_gap_entries' if kind == 'gap' else '_' + kind
            entry = next(e for e in getattr(draft, field) if e.id == key)
            entries = getattr(fresh, field)
            position = next((i for i, e in enumerate(entries) if e.id == key), None)
            if position is None:
                entries.append(entry)
            else:
                entries[position] = entry
            fresh._invalidate_indices(kind)
        return fresh

    def _prefetch(self, calls, index, current_target, blocked_targets):
        """At most one successor; same-target operations wait for actual commit."""
        if index >= len(calls):
            return None
        try:
            name, args = self._parse_item(calls[index])
            if name=='memory_delete':return None
            target = self._dependency_target(name, args)
            if not self._valid_target(name, args) or (target is not None and
                    (target == current_target or target in blocked_targets)):
                return None
        except (ValueError, TypeError, KeyError):
            return None
        attempts = []
        task = asyncio.create_task(self._attempt(name, deepcopy(args), index, 0, attempts))
        self._pipeline_tasks.add(task)
        self._pipeline_attempts[task] = attempts
        return task, attempts

    async def _execute_reviewed(self,response):
        operations=[];outcomes=[];stopped=False
        pipeline = self.review_strategy in (simple_split.STRATEGY,semantic_split.STRATEGY)
        self._split_slot = asyncio.Semaphore(1)
        self._review_slot = asyncio.Semaphore(1)
        self._pipeline_tasks = set()
        self._pipeline_attempts = {}
        self._staged_bases = {}
        prefetched = {}
        expected_generation = self.memory._generation
        blocked_targets=set()
        cycle=self._parts.manifest.cycle_id
        self.last_citation_gate_report={'schema':'pma-live-citation-gate-v1',
            'strategy':self.review_strategy,'repair_limit':self.repair_limit,
            'legacy_policy':'retain_unreviewed_no_freshness_claim',
            'repair_calls':0,'operations':outcomes,'incomplete':False,
            'raw_response_phase1':getattr(response,'content',None),
            'frozen_visibility':visible_snapshot(self._parts)[0]}
        try:
            try:calls=self._tool_items(response)
            except Exception:calls=[('invalid','malformed_tool_response')]
            for index,item in enumerate(calls):
                name='invalid_memory_operation';args=None;operation=None;prepared=None;target=None
                row={'index':index,'cycle_id':cycle,'success':False,'verdict':None,
                     'engineering_status':'not_reviewed','content_status':'not_committed','attempts':[]}
                if index in prefetched:
                    row['attempts'] = prefetched[index][1]
                outcomes.append(row)
                try:
                    name,args=self._parse_item(item)
                    row.update(tool=name,submitted_arguments=deepcopy(args))
                    if self.review_strategy in SPLIT_STRATEGIES:
                        target=self._dependency_target(name,args)
                    if stopped:row['error_code']='not_run_after_review_error'
                    elif self.review_strategy in SPLIT_STRATEGIES and target is not None and target in blocked_targets:
                        row.update(error_code='not_run_failed_target_dependency', blocked_target=target)
                    elif name=='memory_delete' and self.review_strategy!=semantic_split.STRATEGY:
                        row.update(error_code='not_applicable_delete_protocol',preparation='not_reviewed_not_deleted')
                    elif not self._valid_target(name,args):row['error_code']='invalid_operation_or_target'
                    else:
                        base_generation=self.memory._generation
                        if pipeline and base_generation != expected_generation:
                            raise ValueError('stale_operation_base')
                        current=deepcopy(args)
                        for attempt in range(self.repair_limit+1):
                            if self.memory._generation!=base_generation:raise ValueError('stale_operation_base')
                            if pipeline and attempt == 0:
                                pending = prefetched.pop(index, None)
                                if pending is None:
                                    pending = self._prefetch(calls, index, None, blocked_targets)
                                if pending is not None:
                                    task, attempt_rows = pending
                                    row['attempts'] = attempt_rows
                                    # Let the first split acquire its slot before the successor.
                                    await asyncio.sleep(0)
                                    next_pending = self._prefetch(calls, index + 1, target, blocked_targets)
                                    if next_pending is not None:
                                        prefetched[index + 1] = next_pending
                                    result,draft,operation = await task
                                else:
                                    result,draft,operation=await self._attempt(name,current,index,attempt,row['attempts'])
                            else:
                                result,draft,operation=await self._attempt(name,current,index,attempt,row['attempts'])
                            row.update(result)
                            local_parse = self.review_strategy in SPLIT_STRATEGIES and result['engineering_status']=='parse_failure'
                            if result['engineering_status'] not in ('ok','not_reviewed') and not local_parse:
                                stopped=True;break
                            if local_parse:
                                row['failure_scope']='operation_local'
                                original_text = current['reason'] if name == 'memory_delete' else current['content']
                                result['explanation']='Technical parsing failure; no semantic verdict. Original text “'+original_text+'”: '+result.get('reason','invalid model schema')
                                row['explanation']=result['explanation']
                            if result['verdict']=='supported':
                                if pipeline and name!='memory_delete':
                                    if self.memory._generation != expected_generation:
                                        raise ValueError('stale_operation_base')
                                    draft = self._rebase_candidate(draft, operation)
                                prepared=self.memory.prepare_publication(draft)
                                self.memory.publish(prepared)
                                expected_generation = self.memory._generation
                                operation.content_status='committed'
                                row.pop('error_code',None)
                                row.update(success=True,content_status='committed');break
                            if attempt==self.repair_limit:break
                            self.transport_phase='citation_repair'
                            issue={k:result[k] for k in ('error_code','explanation','preparation','repair_feedback') if k in result}
                            if result.get('input'):issue['preparation_issues']=result['input']['preparation']['issues']
                            row['repair']=await repair(self.review_transport,self._maintenance_prompt,name,args,issue,index,
                                                       semantic_v4=self.review_strategy==semantic_split.STRATEGY)
                            self.last_citation_gate_report['repair_calls']+=1
                            if row['repair']['engineering_status']!='ok':
                                row.update(error_code='repair_'+row['repair']['engineering_status'],
                                           engineering_status=row['repair']['engineering_status'])
                                if not (self.review_strategy in SPLIT_STRATEGIES and row['repair']['engineering_status']=='parse_failure'):
                                    stopped=True
                                break
                            replacement=row['repair']['replacement']
                            if replacement['decision']=='withdraw':
                                row.update(withdrawn=True,error_code='author_withdrawn');break
                            current=({**args,'reason':replacement['content'],'evidence':replacement['evidence']}
                                     if name=='memory_delete' else
                                     {**args,'content':replacement['content'],'evidence':replacement['evidence']})
                except Exception as error:
                    if prepared is not None and self.memory.__dict__ is prepared:
                        operation.content_status='committed'
                        row.update(success=True,content_status='committed',post_commit_error=type(error).__name__)
                        stopped=True
                    else:
                        local_invalid = pipeline and args is None and isinstance(error, (ValueError, TypeError, KeyError))
                        row.update(error_code=type(error).__name__,engineering_status='invalid_operation' if local_invalid else 'host_error')
                        stopped = not local_invalid
                if not row['success']:
                    if self.review_strategy in SPLIT_STRATEGIES and target is not None:
                        blocked_targets.add(target)
                    operation=MemoryOperation(name,success=False,error=row['error_code'])
                    operation.content_status='not_committed'
                    row['retained_old_value_may_be_stale']=bool(self.memory.status if name=='memory_update_status'
                        else isinstance(args,dict) and args.get('memory_id'))
                operations.append(operation)
        except BaseException:
            self.last_citation_gate_report.update(incomplete=True,cancelled_or_interrupted=True)
            for row in outcomes:
                if not row['success'] and 'error_code' not in row:
                    row.update(error_code='cancelled_not_committed',engineering_status='cancelled')
                    if row.get('attempts'):
                        row['attempts'][-1]['engineering_status']='cancelled'
            for pending in range(len(outcomes),len(calls)):
                row={'index':pending,'cycle_id':cycle,'success':False,'verdict':None,
                     'engineering_status':'not_run','content_status':'not_committed',
                     'error_code':'not_run_after_cancel'}
                try:
                    name,args=self._parse_item(calls[pending]);row.update(tool=name,submitted_arguments=deepcopy(args))
                except Exception:row['tool']='invalid_memory_operation'
                if pending in prefetched:
                    row['attempts'] = prefetched[pending][1]
                outcomes.append(row)
            raise
        finally:
            # No task survives cancellation, transport failure, or the selection barrier.
            for task in self._pipeline_tasks:
                if not task.done():
                    task.cancel()
            if self._pipeline_tasks:
                await asyncio.gather(*self._pipeline_tasks, return_exceptions=True)
            for task, attempts in self._pipeline_attempts.items():
                if task.cancelled():
                    for attempt in attempts:
                        attempt.update(engineering_status='cancelled', error_code='cancelled_not_committed')
            self._staged_bases.clear()
            try:
                failed=sum(not r['success'] for r in outcomes)
                self.last_citation_gate_report['incomplete'] |= stopped or any(
                    r.get('engineering_status')=='parse_failure' for r in outcomes)
                self.last_evidence_report.update(accepted=not failed,partial_success=bool(failed and failed<len(outcomes)),
                    succeeded=len(outcomes)-failed,failed=failed,operations=deepcopy(outcomes))
                self._previous_failures=[]  # Explicit final receipts replace the old three-error suffix.
                if outcomes:self.pending_receipt=receipt(cycle,outcomes)
                self.last_citation_gate_report.update(final_receipt=deepcopy(self.pending_receipt),
                    receipt_delivery='pending_delivery' if self.pending_receipt is not None else 'none',
                    prior_receipt_deliveries=deepcopy(self.receipt_deliveries))
                if self.review_directory is not None:
                    try:durable(self.review_directory/'gate_cycles.jsonl',self.last_citation_gate_report)
                    except Exception as error:
                        self.last_citation_gate_report.update(incomplete=True,diagnostic_write_error=type(error).__name__,
                            diagnostic_failure=record_failure(self.review_directory, error))
            except Exception as error:
                # Reporting must never erase already-published operation results.
                self.last_citation_gate_report.update(incomplete=True,finalization_error=type(error).__name__,
                    diagnostic_failure=record_failure(self.review_directory, error) if self.review_directory else None)
                fallback={'schema':'pma-host-commit-receipt-v1','cycle_id':cycle,
                    'notice':'Host reporting incomplete; these are commit states, not external facts.',
                    'operations':[{'op_index':r['index'],'outcome':'committed' if r['success'] else 'not_committed',
                        'reason':r.get('error_code','reporting_failed_after_commit'),
                        'target_memory_id':'status' if r.get('tool')=='memory_update_status' else (r.get('submitted_arguments') or {}).get('memory_id'),
                        'memory_id':r.get('candidate',{}).get('memory_id'),
                        'revision_id':r.get('candidate',{}).get('revision_id')} for r in outcomes]}
                fallback['receipt_id']=identity(fallback)
                self.pending_receipt=fallback
                self.last_citation_gate_report['final_receipt']=deepcopy(fallback)
            self._parts=None
            self._draft=None
        return operations
