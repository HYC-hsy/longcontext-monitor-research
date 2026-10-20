"""Candidate-only PMA seams. Pinned PMA bank, CRUD, parser and trigger stay upstream."""
from __future__ import annotations

import hashlib
from copy import deepcopy
from types import SimpleNamespace

from memory_agent.memory.memory_agent import (
    BANK_TOOLS, PHASE1_SYSTEM, PHASE2_SYSTEM, MemoryAgent, MemoryAgentResult,
    MemoryOperation,
)


PHASE2_ADVICE_POLICY = (
    'Current PoS state is a revisable model interpretation, not an observed fact. '
    'Distinguish original task, actual Task/tool observations, historical memory, '
    'your interpretation and optional advice. You may challenge an interpretation '
    'using existing evidence, offer compatible help, withdraw earlier advice or '
    'return <no_intervention/>. Task retains action and completion control. '
    'Do not treat a remembered judgment as authoritative current state.'
)


class ComplementMemoryAgent(MemoryAgent):
    """One current-state owner: PoS. PMA retains knowledge/procedural experience."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._advisory_context = ''
        self.rendered_entry_ids = []
        self.last_phase2_status = None
        self.entry_sources = {}
        self.bank_version = 0
        self._render_phase = None
        self.last_phase1_operations = []
        self.on_render = None

    def _entry_identity(self, entry):
        return {'id': entry.id, 'sha256': hashlib.sha256(
            entry.content.encode('utf-8')).hexdigest(),
            'bank_version': self.entry_sources.get(entry.id, {}).get('bank_version',
                                                                     'unknown')}

    def _format_memory_bank(self, observation=''):
        k_count, p_count = len(self.memory.knowledge), len(self.memory.procedural)
        if k_count + p_count <= self.max_memory_in_prompt or not self.use_bm25_prefilter:
            knowledge, procedural = self.memory.knowledge, self.memory.procedural
            suffix_k = suffix_p = ''
        else:
            knowledge = self.memory.search_knowledge(observation, top_k=20)
            procedural = self.memory.search_procedural(observation, top_k=20)
            suffix_k, suffix_p = f'\n(showing top 20 of {k_count})', f'\n(showing top 20 of {p_count})'
        rendered = {
            'phase': self._render_phase,
            'knowledge': [entry.id for entry in knowledge],
            'procedural': [entry.id for entry in procedural],
            'entries': [self._entry_identity(entry) for entry in [*knowledge, *procedural]],
        }
        self.rendered_entry_ids.append(rendered)
        if self.on_render is not None:
            self.on_render(rendered)
        return ('<memory_bank>\n<knowledge>\n' + self._format_memory_list(knowledge) +
                suffix_k + '\n</knowledge>\n<procedural>\n' +
                self._format_memory_list(procedural) + suffix_p +
                '\n</procedural>\n</memory_bank>')

    async def _call_llm_phase1(self, user_prompt):
        system = PHASE1_SYSTEM.replace(
            '- memory_update_status: Track progress internally (not shown to action agent)\n', '')
        system += '\nCandidate mode: PoS alone maintains current status. Do not call memory_update_status.\n'
        kwargs = dict(prompt=user_prompt, system=system)
        if self.use_structured_tools:
            kwargs['tools'] = [tool for tool in BANK_TOOLS
                               if tool['function']['name'] != 'memory_update_status']
        return await self.llm.call(**kwargs)

    async def _call_llm_phase2(self, user_prompt):
        return await self.llm.call(prompt=user_prompt,
            system=PHASE2_SYSTEM + '\n' + PHASE2_ADVICE_POLICY)

    def _build_phase2_prompt(self, observation, step_count):
        prompt = super()._build_phase2_prompt(observation, step_count)
        if self._advisory_context:
            prompt += '\n## Revisable current-state context (Phase 2 only)\n' + self._advisory_context
        return prompt

    def _parse_tool_calls_from_text(self, text):
        return [(name, args) for name, args in super()._parse_tool_calls_from_text(text)
                if name != 'memory_update_status']

    def _execute_tool_calls(self, response):
        # Original tool names, parser, bank CRUD and operation objects remain in
        # use. The candidate alone narrows fatal errors: a failed bank/capture
        # implementation must not be mistaken for one malformed model argument.
        calls = list(getattr(response, 'tool_calls', None) or [])
        if not calls or any(not self._extract_tool_call(call)[1].get('content')
                            for call in calls):
            raw = self._strip_thinking(getattr(response, 'content', None) or '')
            if '<tool_call>' in raw:
                calls = [SimpleNamespace(function=SimpleNamespace(name=name,
                    arguments=args)) for name, args in self._parse_tool_calls_from_text(raw)]
        operations = []
        self.last_phase1_operations = operations
        for call in calls:
            name, args = self._extract_tool_call(call)
            if not name or name == 'memory_update_status':
                continue
            try:
                if name == 'memory_save_knowledge':
                    content = args.get('content', '')
                    memory_id = self.memory.save_knowledge(content)
                    operations.append(MemoryOperation(action='save_knowledge',
                        memory_id=memory_id, content=content))
                elif name == 'memory_save_procedural':
                    content = args.get('content', '')
                    memory_id = self.memory.save_procedural(content)
                    operations.append(MemoryOperation(action='save_procedural',
                        memory_id=memory_id, content=content))
                elif name == 'memory_delete':
                    memory_id = args.get('memory_id', '')
                    success = self.memory.delete(memory_id)
                    operations.append(MemoryOperation(action='delete',
                        memory_id=memory_id, success=success,
                        error=None if success else 'ID not found'))
            except (TypeError, ValueError, KeyError) as error:
                operations.append(MemoryOperation(action=name, success=False,
                                                  error=str(error)))
            # OSError, RuntimeError, capture and deadline errors propagate with
            # the already committed earlier operations retained on this agent.
        return operations

    async def process(self, observation, step_count=0, *, advisory_context='',
                      input_sources=()):
        """Preserve original two stages, but never swallow whole-stage failure."""
        if not isinstance(advisory_context, str) or len(advisory_context) > 16000:
            raise ValueError('Phase 2 advisory context exceeds candidate budget')
        self._advisory_context = advisory_context
        try:
            self._render_phase = 'phase1'
            prompt1 = self._build_phase1_prompt(observation, step_count)
            response1 = await self._call_llm_phase1(prompt1)
            self.last_phase1_operations = []
            try:
                operations = self._execute_tool_calls(response1)
            finally:
                for operation in self.last_phase1_operations:
                    if operation.success and operation.action in {'save_knowledge', 'save_procedural'}:
                        self.bank_version += 1
                        self.entry_sources[operation.memory_id] = {
                            'bank_version': self.bank_version,
                            'content_sha256': hashlib.sha256(
                                operation.content.encode('utf-8')).hexdigest(),
                            'input_sources': tuple(input_sources),
                            'meaning': 'visible_at_creation_not_sentence_support'}
                    elif operation.success and operation.action == 'delete':
                        self.bank_version += 1
                        self.entry_sources.pop(operation.memory_id, None)
            self._render_phase = 'phase2'
            prompt2 = self._build_phase2_prompt(observation, step_count)
            response2 = await self._call_llm_phase2(prompt2)
            raw2 = getattr(response2, 'content', None) or ''
            reminder = self._parse_phase2_response(raw2)
            self.last_phase2_status = ('reminder' if reminder is not None else
                'no_intervention' if '<no_intervention' in self._strip_thinking(raw2)
                else 'format_rejected')
            return MemoryAgentResult(
                operations=operations, should_inject=reminder is not None,
                context_for_action=reminder,
                raw_response_phase1=getattr(response1, 'content', None),
                raw_response_phase2=raw2,
                reasoning_phase1=getattr(response1, 'reasoning_content', None),
                reasoning_phase2=getattr(response2, 'reasoning_content', None),
                user_prompt_phase1=prompt1, user_prompt_phase2=prompt2)
        finally:
            self._advisory_context = ''
            self._render_phase = None


class SharedViewMemoryAgent(ComplementMemoryAgent):
    """New-mode-only phase scheduler; the released PMA builders still run."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.frozen_selection = None
        self._using_frozen_selection = False

    def _format_memory_bank(self, observation=''):
        if self._using_frozen_selection:
            if self.frozen_selection is None:
                raise RuntimeError('shared-view bank selection was not frozen')
            rendered = deepcopy({key: value for key, value in
                self.frozen_selection.items() if key not in
                {'rendered_text', 'source_mappings'}})
            rendered['phase'] = self._render_phase
            rendered['selection_origin'] = 'frozen_shared_selection'
            self.rendered_entry_ids.append(rendered)
            if self.on_render is not None:
                self.on_render(rendered)
            return self.frozen_selection['rendered_text']
        return super()._format_memory_bank(observation)

    async def phase1(self, observation, step_count, *, input_sources=()):
        self.last_phase1_operations = []
        self.frozen_selection = None
        self._render_phase = 'phase1'
        try:
            prompt = self._build_phase1_prompt(observation, step_count)
            response = await self._call_llm_phase1(prompt)
            try:
                operations = self._execute_tool_calls(response)
            finally:
                # Already successful operations survive a later fatal operation.
                for operation in self.last_phase1_operations:
                    if operation.success and operation.action in {
                            'save_knowledge', 'save_procedural'}:
                        self.bank_version += 1
                        self.entry_sources[operation.memory_id] = {
                            'bank_version': self.bank_version,
                            'content_sha256': hashlib.sha256(
                                operation.content.encode('utf-8')).hexdigest(),
                            'input_sources': tuple(input_sources),
                            'meaning': 'visible_at_creation_not_sentence_support'}
                    elif operation.success and operation.action == 'delete':
                        self.bank_version += 1
                        self.entry_sources.pop(operation.memory_id, None)
            return {'prompt': prompt, 'response': response,
                    'operations': deepcopy(operations)}
        finally:
            self._render_phase = None

    def freeze_selection(self, observation):
        if self.frozen_selection is not None:
            raise RuntimeError('shared-view selection already frozen for this wake')
        self._render_phase = 'shared_selection'
        try:
            rendered_text = super()._format_memory_bank(observation)
            selected = deepcopy(self.rendered_entry_ids[-1])
            selected['rendered_text'] = rendered_text
            selected['bank_version'] = self.bank_version
            selected['source_mappings'] = {
                entry['id']: deepcopy(self.entry_sources.get(entry['id']))
                for entry in selected['entries']}
            self.frozen_selection = selected
            return deepcopy(selected)
        finally:
            self._render_phase = None

    async def phase2(self, observation, step_count, *, advisory_context=''):
        if self.frozen_selection is None:
            raise RuntimeError('shared-view Phase 2 requires frozen history')
        self._advisory_context = advisory_context
        self._render_phase = 'phase2'
        self._using_frozen_selection = True
        try:
            prompt = self._build_phase2_prompt(observation, step_count)
            response = await self._call_llm_phase2(prompt)
            raw = getattr(response, 'content', None) or ''
            reminder = self._parse_phase2_response(raw)
            self.last_phase2_status = ('reminder' if reminder is not None else
                'no_intervention' if '<no_intervention' in self._strip_thinking(raw)
                else 'format_rejected')
            return {'prompt': prompt, 'response': response, 'reminder': reminder,
                    'status': self.last_phase2_status,
                    'selection': deepcopy(self.frozen_selection)}
        finally:
            self._using_frozen_selection = False
            self._advisory_context = ''
            self._render_phase = None
