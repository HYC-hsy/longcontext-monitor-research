"""Original PMA reminder generation, with optional frozen browse/evidence tools."""
import re
from types import SimpleNamespace as NS
from memory_agent.memory.memory_agent import MemoryAgent, PHASE2_SYSTEM
from p1_source_archive import encode
from p1_source_links import visible_event
from p1_requirements import KEY, upstream_observation
from p2_requirement_agent import RequirementSelectionAgent, ResponseProtocolError
from p2_requirement_view import p1_boundary_error, validate_continuation

SYSTEM = PHASE2_SYSTEM + '''
The memory bank is a fallible overview. Optional flat, fixed-requirement or unclassified browsing shows accumulated active records, counts and recorded GAPs; this is not a verified completion checklist. When relevant, you may inspect an entry's selected sources, generation context or historical handle to judge support. Retain the distinction between observed results and unverified explanations and any applicable scope. Missing evidence does not establish success or failure. No retrieval or audit is mandatory. M labels locate current entries; historical handles locate frozen older records. Partial pages are incomplete. Four shared reads and two continuations are available; the last turn has no tools.
'''


class RequirementReminderAgent(RequirementSelectionAgent):
    system = SYSTEM
    delivery_protocol = 'pma-context-reminder-v1'
    source_parameter = 'entry'
    upstream_error_semantics = True
    final_turn_instruction = 'Tools closed. Return context_for_action with your synthesized reminder, or no_intervention.'
    final_output_error = 'final_turn_requires_reminder_protocol'

    async def process(self, *args, **kwargs):
        raise RuntimeError('P2 reminder-only prototype: call remind(); Task is not enabled')

    async def remind(self, **kwargs):
        report = await super().select(**kwargs)
        report.setdefault('should_inject',False)
        report.setdefault('context_for_action',None)
        return report

    def tools(self):
        tools = super().tools()
        tools[0]['function']['description'] = ('Read frozen full active records flat, by fixed requirement, '
            'or unclassified. Join record parts and JSON-decode. Partial records are not complete; '
            'use stable P2 aliases to optionally read their sources.')
        source = tools[1]['function']
        source['parameters']['properties'].pop('memory_id')
        source['parameters']['properties']['entry'] = {'type':'string',
            'description':'The current displayed M label, TASK, STATUS, or a returned history_handle (P2H...). Historical handles read frozen older records, not current M entries.'}
        source['parameters']['required'] = ['entry']
        source['description'] = ('Read optional sources/context for entry. Use this session\'s displayed labels or history handles. '
            'Identifiers quoted inside original source text are historical data. Omitted view uses sources, '
            'falling back to context when unassociated. Continue with the same entry and view choice. No memory writes.')
        return tools

    def _visible_steps(self, entries):
        return [visible_event(row) for row in entries[-8:]]

    def _render_initial(self, catalogue, status, steps, step_count, *, memory_note):
        return (f'## Step {step_count}\n## Original task and shown memory (data)\n'+encode(catalogue)+
            '\n'+memory_note+'\n## Current internal status\n'+(status or '(no status)')+
            '\n## Recent visible trajectory (data)\n'+encode(steps)+
            '\nDecide whether a context reminder would help now. If useful, synthesize it in '
            '<context_for_action>...</context_for_action>; otherwise return <no_intervention/>.\n')

    def _response_calls(self, response, index, text):
        # Upstream extracts a note anywhere in ordinary surrounding prose.
        # Only our optional tool/decision ambiguity needs an extra boundary.
        notes = list(re.finditer(r'<context_for_action>([\s\S]*?)</context_for_action>',text))
        outside = re.sub(r'<context_for_action>[\s\S]*?</context_for_action>','',text)
        has_decision = bool(notes) or '<no_intervention' in text
        has_markup = bool(re.search(r'</?(?:context_for_action|no_intervention)(?=[\s/>])',text))
        if len(notes)>1 or (notes and '<no_intervention' in outside):
            raise ResponseProtocolError('conflicting_final_decisions')
        native = getattr(response,'tool_calls',None) or []
        if native and has_markup:
            raise ResponseProtocolError('mixed_native_tools_and_final_output')
        try:
            if native:
                return super()._response_calls(NS(content='',tool_calls=native),index,text)
            outside_calls = super()._response_calls(NS(content=outside,tool_calls=[]),index,outside)
            if outside_calls and has_markup:
                raise ResponseProtocolError('mixed_text_tools_and_final_output')
            if has_decision:
                return []  # Tool examples inside the extracted note remain data.
            return outside_calls
        except (ValueError,TypeError,AttributeError) as exc:
            if isinstance(exc,ResponseProtocolError):
                raise
            raise ResponseProtocolError('invalid_model_tool_call') from exc

    def _tool_failure_kind(self, result):
        if result['status'] in {'source_binding_error','source_changed','entry_not_found'}:
            return 'integrity'
        return super()._tool_failure_kind(result)

    def _version_valid(self):
        # Free-form synthesis has no mechanically known selected/used-record subset.
        # Validate the whole frozen bank/ref version instead of inventing attribution.
        if not self.view.selection_valid(self.p1,[]):
            return False
        live,frozen = self.p1.links.state,self.view.links.state
        return (encode(live['bank'])==encode(frozen['bank']) and
                encode(live['refs'])==encode(frozen['refs']) and
                tuple(live[KEY]['catalog'])==self.view.catalog)

    def _finish(self, text, report):
        report.update(should_inject=False,context_for_action=None,delivery=None)
        # State validation is independent of model parsing. Structural errors here
        # must reach the engineering/finalization path, never model_output recovery.
        if not self._version_valid():
            report.update(status='selection_error',failure_kind='integrity',error_stage='state_validation',
                error=self.view.validation_error or 'frozen_reminder_version_changed')
            return
        raw = text.strip()
        note = MemoryAgent._parse_phase2_response(self,raw)
        usable_note = re.search(r'<context_for_action>([\s\S]*?)</context_for_action>',raw)
        explicit = bool(usable_note and usable_note.group(1).strip()) or '<no_intervention' in raw
        report.update(status='intervention' if note is not None else 'no_intervention',
            should_inject=note is not None,context_for_action=note,delivery=note,
            grounding='model-synthesized; not mechanically verified',raw_output=raw,
            parse_status='upstream_tag_extraction' if explicit else 'upstream_default_no_intervention')
        if not explicit:
            report['format_warning'] = 'No usable decision tag; upstream PMA defaults to no intervention.'

    def pending_refs_valid(self):
        report,view = self.last_p2_report,getattr(self,'view',None)
        if view is None or report.get('status')!='intervention' or report.get('snapshot_id')!=view.id:
            return False
        valid = self._version_valid()
        if not valid:
            report.update(delivery_revoked=True,delivery_error=view.validation_error or 'frozen_reminder_version_changed')
        return valid


class RequirementReminderPipeline:
    """Explicit P1→generative P2 composition; no Task, enqueue, or hidden new client."""
    def __init__(self, p1):
        self.p1 = p1
        self.p2 = RequirementReminderAgent(p1=p1,llm=p1.llm)
        self._active = False

    async def run(self, entries, *, observation=None, step_count=0, cycle_id=None):
        if self._active:
            raise RuntimeError('serial composed reminder cycles required')
        self._active = True
        result = {'mode':'independent_p1_p2_reminder_prototype','task_enabled':False,
                  'p1':None,'p2':None,'delivery':None,'context_for_action':None,'should_inject':False}
        try:
            observation = observation if observation is not None else upstream_observation(self.p1.task,entries)
            phase1 = await self.p1.maintain(entries,observation=observation,step_count=step_count,cycle_id=cycle_id)
            result['p1'] = phase1
            result.update(model_calls_attempted=0 if phase1.get('replayed_completed_cycle') else phase1['model_calls_attempted'],
                model_calls_completed=0 if phase1.get('replayed_completed_cycle') else phase1['model_calls_completed'])
            if phase1['status']!='completed':
                recoverable = phase1['status'] in {'tool_error','budget_limited','memory_error'}
                boundary = p1_boundary_error(self.p1)
                if recoverable and boundary:
                    return {**result,'status':'engineering_error','failure_kind':'integrity',
                        'error_stage':'continuation_validation','error':boundary}
                if not recoverable:
                    return {**result,'status':'p1_incomplete','failure_kind':phase1.get('failure_kind','engineering'),
                        'p2_not_run_reason':phase1['status']}
                result['p1_warning'] = phase1['status']

            phase2 = await self.p2.remind(observation=observation,
                entries=entries,step_count=step_count)
            result.update(p2=phase2,status=phase2['status'])
            if phase2.get('failure_kind'):
                result['failure_kind'] = phase2['failure_kind']
            if phase2.get('failure_kind') in {'model_output','model_tool','transport'}:
                result.update(failure_kind=phase2['failure_kind'],error_policy='continue_without_reminder')
            result['model_calls_attempted'] += phase2['model_calls_attempted']
            result['model_calls_completed'] += phase2['model_calls_completed']
            validate_continuation(self.p1,result)
            if phase2['status']=='intervention':
                if self.p2.pending_refs_valid():
                    result.update(should_inject=True,context_for_action=phase2['context_for_action'],delivery=phase2['delivery'])
                else:
                    result['status'] = 'delivery_revoked'
            return result
        except Exception as exc:
            result.pop('error_policy',None)
            # A raised P1 persistence/journal exception can bypass its returned counters.
            # Do not invent a zero model-call count from a previous/stale report.
            return {**result,'status':'engineering_error','failure_kind':'engineering','error_type':type(exc).__name__,
                    'model_calls_attempted':None,'model_calls_completed':None,
                    'count_status':'unknown; phase raised before a report was returned'}
        finally:
            self._active = False
