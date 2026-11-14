"""Predictive prompt regression for the prompt-guided loop; no model calls."""
import ast
import hashlib
from pathlib import Path
from memory_agent.memory import read_context_predictive_memory_agent as module

PARENT_SYSTEM = 'You are the task\'s information organizer. Some information that appears during task execution remains valuable much later in the task, while other information only becomes valuable then. Your role is to predict and save this information, and remind the task agent when it is relevant to its current or upcoming work, helping it use existing information to complete the task.\n\nThe <task_description> tags contain the task agent\'s original task, and the <task_trajectory> tags contain the task agent\'s newly observed execution trajectory.\n\nCarry out these steps in this same conversation:\n\n1. Recall and decide the reminder. Use memory_read to read the existing knowledge bank. After receiving its result, consider both the conversation context and the knowledge bank to decide whether to remind the task agent, and what to remind it of, based on its current and upcoming work. Do not save information yet. End this step with exactly one of:\n<context_for_action>\nInformation to remind the task agent of.\n</context_for_action>\n<no_intervention/>\n\n2. Predict and save. When the program advances to this step, you must predict which information received this time will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns, and organize and save that information in the knowledge bank. Before saving, briefly state which information you have selected. The reminder decision has already been recorded and is not changed in this step. Use tools as needed; when finished, reply in ordinary text without a tool call. No completion tag is required. If nothing needs saving, say so in ordinary text.\n\n## Tools\n- memory_add: Save information in the knowledge bank; available during step 2.\n- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.\n'

def restore_parent_prompt(source):
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and getattr(n.targets[0], "id", None) == "REMIND_FIRST_SYSTEM")
    lines = source.splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = ['REMIND_FIRST_SYSTEM = """' + PARENT_SYSTEM + '"""\n']
    return ''.join(lines)

def test_prompt_guided_source_snapshot():
    source = Path(module.__file__).read_text()
    assert hashlib.sha256(restore_parent_prompt(source).encode()).hexdigest() == 'f5a8d15d0520c89f8641be29ccbe1ff8248fbd50eb1fcaa8662b464c60fffb2c'

def test_complete_selected_information_without_new_execution_rules():
    prompt = module.REMIND_FIRST_SYSTEM
    assert "after the task has progressed for another eight turns" in prompt
    assert "fully retain the content needed to understand and use the selected information later" in prompt
    assert "Before saving, briefly state which information you have selected." in prompt
    for removed in ["available during step 2", "The reminder decision has already been recorded",
                    "When the program advances", "No completion tag is required"]:
        assert removed not in prompt
    assert not hasattr(module, "ORGANIZE_START_PROMPT")
