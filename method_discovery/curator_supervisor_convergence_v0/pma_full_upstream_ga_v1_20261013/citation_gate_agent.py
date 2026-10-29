"""Opt-in prepublication gate, with zero/one author repair and final control receipts."""
from copy import deepcopy
import json
from pathlib import Path

from latest_evidence_gap_agent import LatestEvidenceGapMemoryAgent, latest_phase1_system
from evidence_gap_agent import WRITERS
from memory_agent.memory.memory_agent import MemoryOperation
from pma_evidence_review.live_citations import build_live, assess, visible_snapshot
from pma_evidence_review.prompt_strategy import ONE_SENTENCE
from pma_evidence_review.claim_split import STRATEGY as CLAIM_SPLIT
from pma_evidence_review.gate_control import repair, receipt
from pma_evidence_review.citation_inputs import identity
from pma_evidence_review.transport import CapturedTransport, durable


class CitationGateMemoryAgent(LatestEvidenceGapMemoryAgent):
    def __init__(self, *, review_directory=None, run_id='live', repair_limit=0,
                 review_strategy=ONE_SENTENCE, **kwargs):
        if review_strategy not in (ONE_SENTENCE, CLAIM_SPLIT):raise ValueError('review_strategy')
        self.review_strategy=review_strategy
        if type(repair_limit) is not int or repair_limit not in (0,1):raise ValueError('repair_limit')
        super().__init__(**kwargs)
        self._tools=deepcopy(self._tools)
        for tool in self._tools:
            function=tool['function']
            if function['name'] in WRITERS:
                function['description']='Propose a memory write; only the host commit receipt confirms publication. '+function['description']
            elif function['name']=='memory_delete':
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
        if name not in WRITERS or not isinstance(args,dict):return False
        allowed={'content','evidence'} | ({'memory_id'} if WRITERS[name]!='status' else set())
        if not set(args)<=allowed or not isinstance(args.get('content'),str) or not args['content'].strip():return False
        if 'memory_id' in args:
            key=args['memory_id']
            if not isinstance(key,str) or not key:return False
            try:return self.memory._content(key)[0]==WRITERS[name]
            except ValueError:return False
        return True

    async def _attempt(self,name,args,index,attempt,attempts):
        row={'attempt':attempt,'verdict':None,'engineering_status':'not_reviewed','success':False}
        attempts.append(row)
        if name=='memory_update_status' and len(args['content'])>self.memory._max_status_length:
            row.update(error_code='status_would_truncate',preparation='status_would_truncate')
            return row,None,None
        draft=self._operation_draft()
        operation=self._apply_operation(draft,name,args,index)
        operation.content_status='candidate_not_published'
        row['candidate']=deepcopy(vars(operation))
        envelope,request=build_live(draft,self._parts,operation,index,run_id=self.run_id,review_strategy=self.review_strategy)
        row.update(candidate=deepcopy(vars(operation)),input=envelope,request=request,
                   preparation=envelope['preparation']['status'])
        if request is None:row['error_code']='citation_preparation_'+row['preparation']
        else:
            self.transport_phase='citation_review'
            row.update(await assess(request,self.review_transport))
            if row['engineering_status']!='ok':row['error_code']='citation_'+row['engineering_status']
            elif row['verdict']!='supported':row['error_code']='citation_'+row['verdict']
        return row,draft,operation

    async def _execute_reviewed(self,response):
        operations=[];outcomes=[];stopped=False
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
                name='invalid_memory_operation';args=None;operation=None;prepared=None
                row={'index':index,'cycle_id':cycle,'success':False,'verdict':None,
                     'engineering_status':'not_reviewed','content_status':'not_committed','attempts':[]}
                outcomes.append(row)
                try:
                    name,args=self._parse_item(item)
                    row.update(tool=name,submitted_arguments=deepcopy(args))
                    target='status' if name=='memory_update_status' else (args.get('memory_id') if isinstance(args,dict) else None)
                    if stopped:row['error_code']='not_run_after_review_error'
                    elif self.review_strategy==CLAIM_SPLIT and target in blocked_targets:
                        row.update(error_code='not_run_failed_target_dependency', blocked_target=target)
                    elif name=='memory_delete':
                        row.update(error_code='not_applicable_delete_protocol',preparation='not_reviewed_not_deleted')
                    elif not self._valid_target(name,args):row['error_code']='invalid_operation_or_target'
                    else:
                        base_generation=self.memory._generation
                        current=deepcopy(args)
                        for attempt in range(self.repair_limit+1):
                            if self.memory._generation!=base_generation:raise ValueError('stale_operation_base')
                            result,draft,operation=await self._attempt(name,current,index,attempt,row['attempts'])
                            row.update(result)
                            local_parse = self.review_strategy==CLAIM_SPLIT and result['engineering_status']=='parse_failure'
                            if result['engineering_status'] not in ('ok','not_reviewed') and not local_parse:
                                stopped=True;break
                            if local_parse:
                                row['failure_scope']='operation_local'
                                result['explanation']='Technical parsing failure; no semantic verdict. Original text “'+current['content']+'”: '+result.get('reason','invalid model schema')
                                row['explanation']=result['explanation']
                            if result['verdict']=='supported':
                                prepared=self.memory.prepare_publication(draft)
                                self.memory.publish(prepared)
                                operation.content_status='committed'
                                row.pop('error_code',None)
                                row.update(success=True,content_status='committed');break
                            if attempt==self.repair_limit:break
                            self.transport_phase='citation_repair'
                            issue={k:result[k] for k in ('error_code','explanation','preparation') if k in result}
                            if result.get('input'):issue['preparation_issues']=result['input']['preparation']['issues']
                            row['repair']=await repair(self.review_transport,self._maintenance_prompt,name,args,issue,index)
                            self.last_citation_gate_report['repair_calls']+=1
                            if row['repair']['engineering_status']!='ok':
                                row.update(error_code='repair_'+row['repair']['engineering_status'],
                                           engineering_status=row['repair']['engineering_status'])
                                if not (self.review_strategy==CLAIM_SPLIT and row['repair']['engineering_status']=='parse_failure'):
                                    stopped=True
                                break
                            replacement=row['repair']['replacement']
                            if replacement['decision']=='withdraw':
                                row.update(withdrawn=True,error_code='author_withdrawn');break
                            current={**args,'content':replacement['content'],'evidence':replacement['evidence']}
                except Exception as error:
                    if prepared is not None and self.memory.__dict__ is prepared:
                        operation.content_status='committed'
                        row.update(success=True,content_status='committed',post_commit_error=type(error).__name__)
                        stopped=True
                    else:
                        row.update(error_code=type(error).__name__,engineering_status='host_error')
                        stopped=True
                if not row['success']:
                    if self.review_strategy==CLAIM_SPLIT and isinstance(args,dict):
                        target='status' if name=='memory_update_status' else args.get('memory_id')
                        if target is not None:blocked_targets.add(target)
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
                outcomes.append(row)
            raise
        finally:
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
                        self.last_citation_gate_report.update(incomplete=True,diagnostic_write_error=type(error).__name__)
            except Exception as error:
                # Reporting must never erase already-published operation results.
                self.last_citation_gate_report.update(incomplete=True,finalization_error=type(error).__name__)
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
