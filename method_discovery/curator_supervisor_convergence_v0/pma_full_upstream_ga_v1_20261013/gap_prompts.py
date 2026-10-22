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
"""

ATTENTION = """
The gap view is fallible memory from Phase 1, not certified truth. Read it with the
original task, current trajectory, and ordinary memory when deciding whether and
what to remind. If the agent is already addressing a gap or no new help is useful,
remain silent; a gap does not force a reminder. Keep the original
context_for_action/no_intervention output protocol.
"""


def phase2_system():
    return PHASE2_SYSTEM + ATTENTION

