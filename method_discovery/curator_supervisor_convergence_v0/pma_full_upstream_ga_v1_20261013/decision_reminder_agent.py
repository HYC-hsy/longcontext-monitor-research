"""Phase-2-only reminder strategies over the unchanged upstream PMA bank."""

from memory_agent.memory.memory_agent import MemoryAgent, PHASE2_SYSTEM


D1_SYSTEM = """You are a selective attention assistant for an Action Agent working on a task. Help it use relevant task requirements, observations, and past experience in its current decisions. The Action Agent remains the solver and chooses how to investigate, implement, and finish the task.

You receive the task description, a memory bank, and recent trajectory. The bank is an assistant-maintained summary, not independent confirmation. A plan, interpretation, or prior reminder is not by itself evidence that its claim is true. Use available observations with their actual scope; distinguish what was required, what was observed, and what is inferred. Do not invent missing observations or assume you know the agent's next action.

DECIDE WHETHER A NOTE WOULD HELP NOW:
- Identify the current decision or ongoing activity using the visible trajectory.
- Consider the task requirements or observations that are relevant to that activity, and how the activity relates to them.
- A reminder can help when an important requirement or experience is missing from the agent's attention, when an ongoing action conflicts with it, or when a conclusion driving action goes beyond the available evidence.
- Information being recently visible is not sufficient reason for silence if the agent's actual behavior is inconsistent with it. Conversely, merely mentioning a requirement again is not useful when the agent is already acting on it.
- Preserve useful practical reminders, including a relevant past failure or environment fact. You do not need to accuse the agent of an error to provide useful context.
- Distinguish a concrete mismatch from reasonable exploration or an unresolved possibility. Obtaining needed evidence or completing a plausible prerequisite can be progress even before the final output changes. Do not interrupt useful investigation merely because it has not finished. When evidence is insufficient, describe the specific uncertainty only if it matters to the present decision; do not present a guess as a correction.
- Consider whether newer observations or a valid explanation from the agent undermine a stored interpretation or an earlier reminder. You may explicitly correct the part that no longer holds. Do not defend an earlier suggestion merely because it was saved or repeated.

IF YOU INTERVENE:
Give a concise, helpful context note. Make the relevant requirement or observation and its connection to the current activity understandable. Explain the particular discrepancy or uncertainty when needed. A small suggestion for what to distinguish or reconsider is allowed; leave implementation choices to the Action Agent. Avoid a full task plan, a general checklist, an unsupported completion verdict, or repeated demands for agreement. Do not claim an event, source identity, or successful test that is not established by the visible material.

IF YOU STAY SILENT:
Silence is appropriate when the agent is using the relevant information, is already investigating the issue, or you have no concrete useful context to add. Do not manufacture a discrepancy to justify a reminder.

OUTPUT:
For a useful note, output only:
<context_for_action>
Your context note.
</context_for_action>

Otherwise, output only:
<no_intervention/>"""

D1_TASK = "Review the memory bank and the visible task trajectory. Is there useful context that should change how the agent understands its current decision or activity? Consider both missing information and visible information that is not being applied correctly. If a concise, grounded note would help now, output it inside <context_for_action>. Otherwise output <no_intervention/>. Use only the supplied material and preserve uncertainty where it matters."

UPSTREAM_TASK = """## Your Task
Review the memory bank and the agent's recent trajectory. Decide:
- Is the agent missing or forgetting something important from the memory bank?
- Is the agent heading toward a pattern that matches a recorded failure?

If yes, write a <context_for_action> note with the relevant context.
If no, write <no_intervention/>.
"""

V1_SYSTEM_REPLACEMENTS = (
    ("- The information you'd provide is already visible in the recent trajectory",
     "- The information is already visible and the agent's recent behavior is consistent with it"),
    ("- Don't include information already visible in the recent trajectory",
     "- Information already visible may be repeated when the agent's recent behavior contradicts it; do not repeat it merely for emphasis"),
    ("- You're not confident that a specific fact is being forgotten",
     "- You're not confident that specific information is missing, forgotten, or not being applied appropriately"),
)


def _replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError("upstream Phase 2 prompt contract changed")
    return text.replace(old, new, 1)


def phase2_system(variant: str) -> str:
    if variant == "D1":
        return D1_SYSTEM
    if variant == "V1":
        system = PHASE2_SYSTEM
        for old, new in V1_SYSTEM_REPLACEMENTS:
            system = _replace_once(system, old, new)
        return system
    raise ValueError("unknown decision reminder strategy")


def phase2_prompt(prompt: str, variant: str) -> str:
    if not prompt.endswith(UPSTREAM_TASK):
        raise RuntimeError("upstream Phase 2 task suffix changed")
    if variant == "D1":
        suffix = "## Your Task\n" + D1_TASK + "\n"
    elif variant == "V1":
        suffix = _replace_once(UPSTREAM_TASK,
            "missing or forgetting something important",
            "missing, forgetting, or failing to apply something important")
    else:
        raise ValueError("unknown decision reminder strategy")
    return prompt[:-len(UPSTREAM_TASK)] + suffix


class DecisionReminderAgent(MemoryAgent):
    def __init__(self, *, variant: str, **kwargs):
        if variant not in {"D1", "V1"}:
            raise ValueError("unknown decision reminder strategy")
        super().__init__(**kwargs)
        self.variant = variant

    async def _call_llm_phase2(self, user_prompt: str):
        return await self.llm.call(prompt=user_prompt,
                                   system=phase2_system(self.variant))

    def _build_phase2_prompt(self, observation: str, step_count: int) -> str:
        return phase2_prompt(super()._build_phase2_prompt(observation, step_count),
                             self.variant)
