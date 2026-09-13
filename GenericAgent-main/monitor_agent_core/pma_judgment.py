"""Local judgment-basis adaptation; upstream memory execution stays unchanged."""
import copy


MAINTENANCE = '''
Maintain a revisable basis for judgment, not a completion scoreboard. Keep explicit task requirements
distinct from implementation claims and observations. For a consequential judgment, retain the evidence
source, what it actually establishes, and any plausible alternative it does not yet rule out. Note what
observation could change the judgment when useful; do not invent objections or fill a fixed form.
Simple facts can remain simple. Update status with supported progress and important unresolved grounds.
Printed assertions, echoed checkmarks and old notes remain assertions even inside successful tool output.
Read the producing command alongside its output. Repetition or storage does not add independent support.
Revise stale conclusions when newer evidence challenges them; preserve relevant requirements.
'''

COMPARISON = '''
Compare recent behavior with the task and the updated basis for judgment. In addition to forgotten facts
and repeated mistakes, notice conclusions whose evidence cannot distinguish the required behavior from
a plausible failure. Suggest a small discriminating observation when it would change an important
decision. Do not require testing every unknown or repeat resolved concerns. A test's expectation must
itself be supported by the task; a passing test or successful command is not automatically sufficient.
Your output is a lead for the persistent monitor, not proof or mandatory intervention. Retain the original
context_for_action / no_intervention output protocol.
'''


def adapt(system, tools):
    if not tools:
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
