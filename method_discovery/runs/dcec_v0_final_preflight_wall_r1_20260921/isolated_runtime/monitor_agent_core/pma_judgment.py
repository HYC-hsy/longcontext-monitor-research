"""Local judgment-basis adaptation; upstream memory execution stays unchanged."""
import copy
from .vendor.pma_memory.memory_agent import MemoryAgent


MAINTENANCE = '''
Organize evidence for the next judgment, rather than deciding task completion during maintenance.
Keep explicit requirements, reported claims, actual changes and observations distinct. Attribute a claim
of completion to its speaker instead of converting it into an established fact. Keep what was inspected,
its source and scope, and important unresolved grounds. Simple facts remain simple; no fixed form is needed.
Compare observation time with modification time: an old check followed by a successful write is not
evidence that the write failed. Overlapping or unknown timing cannot settle that question. Preserve
the uncertainty rather than inventing a filesystem failure or a general lesson from it.
Printed assertions, echoed checkmarks and old notes remain assertions even inside successful tool output.
Read the producing command alongside its output. Repetition or storage does not add independent support.
Revise stale conclusions when newer evidence challenges them; preserve relevant requirements.
'''

COMPARISON = '''
Start from the original requirement relevant to the current decision. Before accepting the memory's
conclusion, determine what an observation would have to establish to support that requirement. Then
compare what the available checks actually establish, including their scope and time. Similar names,
partial coverage or compliance with earlier advice need not establish the original requirement.
If a concrete important gap changes the current decision, suggest a small discriminating observation.
Do not enumerate every untested possibility. Moving to another subtask and declaring the whole task
complete need different support. A test's expectation must itself be supported by the task.
Your output is a lead for the persistent monitor, not proof or mandatory intervention. Retain the original
context_for_action / no_intervention output protocol.
'''


class JudgmentMemoryAgent(MemoryAgent):
    """Adapt input order and local responsibilities, retaining author process/operations."""
    def _build_phase1_prompt(self, observation, step_count):
        return (f'## Step {step_count}\n## Context\n{observation}\n'
                f'## Prior memory\n{self._format_memory_bank(observation)}\n'
                '## Your Task\nOrganize requirements, claims, changes and timed observations for '
                'subsequent judgment. Update or remove stale entries with the existing bank tools; '
                'do not pre-decide completion. Keep only useful durable information.')

    def _build_phase2_prompt(self, observation, step_count):
        return (f'## Step {step_count}\n## Original task and recent evidence\n{observation}\n'
                f'## Updated memory (revisable, not an authority)\n{self._format_memory_bank(observation)}\n'
                '## Your Task\nStart with the relevant original requirement and what would support it, '
                'then assess the available evidence. For a concrete decision-relevant gap or forgotten '
                'requirement, output <context_for_action> with a useful lead. Otherwise output '
                '<no_intervention/>. Neither output certifies whole-task completion.')


def adapt(system, tools):
    if not tools:
        system = system.replace('1. Review the memory bank contents\n2. Review the agent\'s recent trajectory (what it\'s doing now)',
            '1. Read the relevant original requirement and establish what would support it\n'
            '2. Compare recent evidence and the revisable memory against that requirement')
        system = system.replace('- The agent\'s actions are consistent with memory bank contents',
            '- The actions and judgments are adequately supported by the task and observations')
        system = system.replace("- You're not confident that a specific fact is being forgotten",
            "- You have no concrete basis for a forgotten fact or an unsupported consequential judgment")
        return system + '\n' + COMPARISON, tools
    adapted = copy.deepcopy(tools)
    system = system.replace('Track progress internally (not shown to action agent)',
        'Maintain revisable progress and its grounds (available to the persistent monitor)')
    for tool in adapted:
        function = tool['function']
        if function['name'] == 'memory_update_status':
            function['description'] = 'Update revisable progress, its evidence basis and important unresolved grounds.'
            function['parameters']['properties']['content']['description'] = 'Natural judgment summary, not a completion scoreboard.'
    return system + '\n' + MAINTENANCE, adapted
