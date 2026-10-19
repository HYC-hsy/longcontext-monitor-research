"""Candidate-only PMA seams. Pinned PMA bank, CRUD, parser and trigger stay upstream."""
from __future__ import annotations

from types import SimpleNamespace

from memory_agent.memory.memory_agent import (
    BANK_TOOLS, PHASE1_SYSTEM, PHASE2_SYSTEM, MemoryAgent, MemoryAgentResult,
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

    def _format_memory_bank(self, observation=''):
        k_count, p_count = len(self.memory.knowledge), len(self.memory.procedural)
        if k_count + p_count <= self.max_memory_in_prompt or not self.use_bm25_prefilter:
            knowledge, procedural = self.memory.knowledge, self.memory.procedural
            suffix_k = suffix_p = ''
        else:
            knowledge = self.memory.search_knowledge(observation, top_k=20)
            procedural = self.memory.search_procedural(observation, top_k=20)
            suffix_k, suffix_p = f'\n(showing top 20 of {k_count})', f'\n(showing top 20 of {p_count})'
        self.rendered_entry_ids.append({
            'knowledge': [entry.id for entry in knowledge],
            'procedural': [entry.id for entry in procedural],
        })
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
        calls = []
        for call in getattr(response, 'tool_calls', None) or []:
            name, _args = self._extract_tool_call(call)
            if name != 'memory_update_status':
                calls.append(call)
        clean = SimpleNamespace(content=getattr(response, 'content', None), tool_calls=calls)
        return super()._execute_tool_calls(clean)

    async def process(self, observation, step_count=0, *, advisory_context=''):
        """Preserve original two stages, but never swallow whole-stage failure."""
        if not isinstance(advisory_context, str) or len(advisory_context) > 16000:
            raise ValueError('Phase 2 advisory context exceeds candidate budget')
        self._advisory_context = advisory_context
        try:
            prompt1 = self._build_phase1_prompt(observation, step_count)
            response1 = await self._call_llm_phase1(prompt1)
            operations = self._execute_tool_calls(response1)
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
