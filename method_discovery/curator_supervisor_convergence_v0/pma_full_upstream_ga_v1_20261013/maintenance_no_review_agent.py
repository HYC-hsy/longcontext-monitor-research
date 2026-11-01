"""Explicit maintenance candidate: latest writes plus the existing tag selector."""
from latest_evidence_gap_agent import LatestEvidenceGapMemoryAgent, latest_phase1_system
from verbatim_selection_mixin import VerbatimSelectionMixin


from citation_gate_config import MAINTENANCE_POLICY as POLICY


MAINTENANCE_RULES = """
Maintain existing memory from the new material first. For the same object, scope,
and future use, decide whether an existing record should be revised before adding
another. Add only when no corresponding record exists and the information helps
continued work; leave unchanged records alone. Do not force one fact per entry or
merge different environments or different problems merely because they look alike.

Knowledge should retain specific reusable results, constraints and partial results.
Experiences should retain what was tried and the observed outcome; include a cause
only when the available material supports it. A later success need not erase a
useful earlier failure. Preserve object, time, version, conditions and scope.
Keep status short but sufficient for current progress and relevant next steps,
without recopying the entire build or debugging history. Keep gaps focused on the
specific unresolved condition, without repeating its full completion history.

Unknown or unverified is not observed failure. A plan or promise is not execution;
a local result is not whole-task completion. Interpret output with the action that
produced it and the actual results. An agent's self-report, a comment or a success
string printed by its own script (including echo) is a claim, not proof that the
check succeeded. Keep confirmed observations distinct from tentative conclusions.
Record only concrete task-relevant unresolved conditions; do not enumerate
hypothetical risks or invent requirements. No additional diagnosis is required.
"""


SCOPED_GAP_MAINTENANCE = """
Maintain a separate gap view with memory_save_gap. At initialization, retain only
acceptance expectations supported by the original task.

Test-quality checks:
When visible work creates, changes or runs tests, or claims completion, inspect
what behavior and scope were checked, what would make the check fail, and whether
actual outputs support the claim. Record a specific supported discrepancy:
relevant missing coverage, weak assertions, wrong expectations, input contracts,
or checks of the wrong behavior. A defective check does not prove a defective
implementation. Do not invent requirements, unseen test behavior, thresholds or
checklists of hypothetical edge cases.

Compare new observations with affected gaps. Retire a displayed ID only when its
condition is resolved within scope, obsolete, redundant or unsupported. A plan,
acknowledgment or success claim alone is not resolution. If partly resolved,
revise the same ID to retain the remaining condition. Status updates do not close
gaps. Preserve useful corrective action and observed verification as a concise,
scoped experience; retiring duplicate or unsupported gaps is not a successful
repair. Do not save entries to narrate memory edits or relist unchanged gaps.
"""


def maintenance_system():
    # Replace conflicting inherited guidance at its source in the assembled
    # candidate prompt; historical modes and pinned vendor bytes stay unchanged.
    text = latest_phase1_system()
    replacements = (
        ("3. **Record failures**: What was tried, why it failed, what the error was — so it's not repeated",
         "3. **Record experiences**: What was tried and what happened; include why only when supported"),
        ("4. **Keep it lean**: Revise superseded entries using their stable memory_id; delete only to retire an entry",
         "4. **Maintain first**: Revise corresponding entries with their stable memory_id; delete only to retire an entry"),
        ("5. **Don't save obvious things**: Terminal output the agent just saw, general knowledge about tools",
         "5. **Preserve useful observations**: Keep important tool results, failures and partial conclusions that will matter after the recent window; omit incidental output and general tool knowledge"),
        ("## What to save at Step 1 (task description):", MAINTENANCE_RULES + "\n## What to save at Step 1 (task description):"),
        ("Bindings are exact_unique, exact_multiple, normalized_unique, normalized_multiple,\nfuzzy_candidate, unbound, or error. None proves truth or entailment. Normalized\nmatches are not verbatim quotes; fuzzy candidates are approximate locations, not\nverified support. Multiple locations are alternatives, not corroboration.\nAlignment scores describe text matching, not probabilities that content is true.",
         "Source bindings locate text; they do not prove truth or entailment. Approximate matches are not verified quotations; multiple locations are alternatives, not corroboration."),
    )
    for old, new in replacements:
        if text.count(old) != 1:
            raise RuntimeError('maintenance_prompt_anchor_changed')
        text = text.replace(old, new, 1)
    # Consolidate the inherited GAP maintenance block, rather than accumulating
    # another overlapping history/lifecycle checklist beside the new rules.
    start_anchor = '\nMaintain a separate gap view'
    end_anchor = '\nWrite content normally; evidence is optional:'
    if text.count(start_anchor) != 1 or text.count(end_anchor) != 1:
        raise RuntimeError('maintenance_prompt_anchor_changed')
    start = text.index(start_anchor)
    end = text.index(end_anchor, start)
    return text[:start] + SCOPED_GAP_MAINTENANCE + text[end:]


class MaintenanceNoReviewAgent(VerbatimSelectionMixin, LatestEvidenceGapMemoryAgent):
    """No gate transport, split, review, repair, proposals or semantic veto."""
    maintenance_policy = POLICY

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        descriptions = {
            'memory_save_knowledge': 'Save or revise specific useful facts, constraints or partial results; preserve their scope and conditions.',
            'memory_save_procedural': 'Save or revise an experience: what was tried and the observed outcome. Include causes only when supported by available material.',
            'memory_update_status': 'Replace internal progress with a short sufficient current summary and relevant next steps; keep plans distinct from executed results.',
            'memory_save_gap': 'Save or revise a concrete unresolved task condition, not its full history. Unknown or unverified does not mean failed.',
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
