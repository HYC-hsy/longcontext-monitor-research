"""Natural-language additions; no parsed gap labels or completion gate."""

from memory_agent.memory.memory_agent import PHASE2_SYSTEM


MAINTENANCE = """
Maintain a separate gap view with memory_save_gap(content), using natural language.
Record task-related unknown information, unmet goals, acceptance requirements still
awaiting verification, and observed defects in tests. At initialization, record only
acceptance expectations supported by the original task, not a generic checklist.
Unverified does not mean failed; work not yet done may be an unmet goal. Test defects
may include missing relevant coverage, weak assertions, wrong expectations, input
contract errors, or execution that did not check the intended behavior. Do not invent
requirements or present an inference as an observed fact.
Save and delete update the view immediately. To revise, delete the displayed real gap
ID and save a new entry; never guess a new ID. Unmentioned entries remain. Do not
output a whole state table, complex JSON, or a repeated list of known gaps.

Test-quality checks:
When the recent trajectory contains test creation, modification, execution, or a
completion claim, inspect the relevant visible checks and results. Ask what task
behavior and scope the check covers, what would make it fail, and whether its
actual output supports the claimed success. Consider missing relevant coverage,
weak assertions, and contradictions between raw results and derived summaries.
Record a concrete, task-relevant discrepancy as a gap when supported by evidence.
Distinguish a defective check from a defective implementation: one does not prove
the other. Do not invent acceptance requirements, arbitrary coverage thresholds,
or unseen test behavior. Do not create a generic checklist or a gap for every
hypothetical edge case. Keep the existing initialization behavior.

Maintain existing gaps:
Compare new evidence with affected existing gaps, not just the progress status.
If evidence resolves the stated gap within its scope, delete that displayed gap
ID. If only part is resolved, revise it using the existing delete-and-save tools
so the unresolved part remains. Correct obsolete paths and remove duplicate or
unsupported entries when justified. Acknowledgment, a plan, or a success claim
alone is not resolution evidence. Do not close broader or unrelated gaps merely
because one check succeeded. Updating status does not update or remove gaps.

Preserve useful resolutions:
When a resolved gap yields a useful debugging experience that would otherwise be
lost, use memory_save_procedural to record the problem, corrective action, observed
verification result, and applicable scope concisely. Use available step references
when helpful; do not invent references. Correct related stored claims when new
evidence supersedes them, using the existing memory tools. Do not save an entry
merely to announce a memory edit. Deleting a duplicate, obsolete, or unsupported
gap is not a successful repair and must not be recorded as one.
Use only necessary tool calls for changes; do not output a full per-gap review
checklist or repeat unchanged entries.
"""

ATTENTION = """
The gap view is fallible memory from Phase 1, not certified truth. Read it together
with the original task, current trajectory, and ordinary memory. A stored claim
or progress summary is not stronger evidence than the observations it summarizes.
Do not turn an agent's self-description, a limited search, or an inference into a
verified fact. Preserve the scope and uncertainty of the available evidence.

Visible information can still warrant a reminder when the agent's current
conclusion or action materially conflicts with the original requirement or the
available evidence. For test-quality gaps, identify the specific discrepancy
between what was checked, what happened, and what was claimed. Do not conclude
that the implementation failed merely because its checking script is unreliable.

Remain selective. If the agent is already addressing the issue appropriately,
or no concrete task-relevant help is warranted, remain silent. If sufficient
evidence already resolves a gap, do not ask the Task agent to repeat that work
solely because the old gap entry remains. Do not treat the existence of a gap as
a mandatory reminder or a completion veto. Keep the original
context_for_action/no_intervention output protocol.
"""

PHASE2_REPLACEMENTS = (
    (
        "- The information you'd provide is already visible in the recent trajectory",
        "- The information is already visible in the recent trajectory and is being applied appropriately",
    ),
    (
        "- Don't include information already visible in the recent trajectory",
        "- Avoid repeating visible information unless it identifies a concrete, task-relevant omission or misapplication of evidence",
    ),
    (
        "- You're not confident that a specific fact is being forgotten",
        "- You cannot identify a concrete task-relevant omission or contradiction supported by the available evidence",
    ),
)


def phase2_system():
    text = PHASE2_SYSTEM
    for old, new in PHASE2_REPLACEMENTS:
        text = text.replace(old, new, 1)
    return text + ATTENTION

