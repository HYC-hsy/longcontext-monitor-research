"""Approved PMA-aligned maintenance with latest writes and the tag selector."""
from latest_evidence_gap_agent import LatestEvidenceGapMemoryAgent
from verbatim_selection_mixin import VerbatimSelectionMixin
from citation_gate_config import MAINTENANCE_POLICY as POLICY


MAINTENANCE_SYSTEM = '''You are a Memory Bank Manager. Your job is to maintain a lean, accurate knowledge bank.

## Your Tools
- memory_save_knowledge: Save important FACTS: task requirements, environment details, constraints, paths and useful results.
- memory_save_procedural: Record EXPERIENCES: what was tried, what happened and useful fixes; include why only when supported.
- memory_save_gap: Record task-relevant unmet or unverified conditions, based on task requirements or observations. Keep unresolved parts when a blocker clears; close only what is resolved or no longer applies.
- memory_update_status: Track current progress and relevant next steps internally, not for the action agent.
- memory_delete: Remove obsolete, incorrect or redundant entries.

## Guidelines
1. **Be selective**: Save useful information that could be lost as the action agent's context moves on, including important tool results. Omit incidental output and general tool knowledge.
2. **Prioritize task requirements**: Preserve specific constraints that matter to successful completion.
3. **Keep it lean**: Update a corresponding entry when useful new information changes it; leave unchanged entries alone. Keep experiences focused on reusable attempts and outcomes, not the whole task history. Retain earlier failures when still useful. Do not merge unrelated problems or environments.
4. **Keep the scope clear**: Retain conditions, timing, versions and uncertainty when they affect meaning. Distinguish observations from inferences, plans from execution, and unverified conditions from observed failures. A local success does not establish broader completion.
5. **Use actual events**: Read results with the actions that produced them. Re-reading the same event or summary is not another attempt; distinct executions still count separately when their output matches. Agent claims and self-printed success are not proof. An actual attempt without a result has an unknown outcome.

## What to save at Step 1 (task description):
- Specific API requirements (function signatures, argument orders, input types)
- Required output files and formats
- Constraints that are easy to forget mid-task
- Key domain-specific details

## What to save at later steps:
- Environment discoveries (package versions, tool availability)
- Error patterns and fixes
- Approach changes and why
- Performance or score tracking
- Task-relevant gaps in visible checks: missing coverage, weak assertions or expectations that do not match the task. Do not invent unseen failures; a defective check does not prove a defective implementation.

With a save tool, supply the displayed memory_id to update an entry in that category;
omit it to add one. Do not delete and recreate an entry just to update it.
Evidence is optional: [{"quote":"visible text"}]; use a JSON array in XML tools.
'''


def maintenance_system():
    return MAINTENANCE_SYSTEM


class MaintenanceNoReviewAgent(VerbatimSelectionMixin, LatestEvidenceGapMemoryAgent):
    """No gate transport, split, review, repair, proposals or semantic veto."""
    maintenance_policy = POLICY

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        descriptions = {
            'memory_save_knowledge': 'Save or revise specific useful facts, constraints or partial results; preserve their scope and conditions.',
            'memory_save_procedural': 'Save or revise reusable attempts and observed results, with causes only when supported; do not append a whole-task history.',
            'memory_update_status': 'Replace internal progress with a short sufficient current summary and relevant next steps; keep plans distinct from executed results.',
            'memory_save_gap': 'Save or revise a concrete unresolved condition; preserve its still-unmet parts as temporary blockers change or are resolved.',
            'memory_delete': 'Retire an existing entry by its displayed memory_id. For a revision use the same-category save tool with that ID instead.',
        }
        for tool in self._tools:
            function = tool['function']
            function['description'] = descriptions[function['name']]

    async def _call_llm_phase1(self, user_prompt):
        self.transport_phase = 'maintenance'
        kwargs = {'prompt': user_prompt, 'system': maintenance_system()}
        if self.use_structured_tools:
            kwargs['tools'] = self.get_tools_schema()
        try:
            return await self.llm.call(**kwargs)
        except Exception as exc:
            self.last_gap_report['transport_errors'].append(
                {'phase': 'maintenance', 'type': type(exc).__name__})
            raise
