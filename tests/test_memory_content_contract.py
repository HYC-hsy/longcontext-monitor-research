"""Description-only change; synthetic calls establish fidelity, not model quality."""
import ast
import copy
import hashlib
from pathlib import Path

from test_predictive_memory_read import Script, call, response, run
from test_remind_first_loop import read, decision, done
from test_predictive_tool_recovery import block_network  # noqa: F401
from memory_agent.memory import read_context_predictive_memory_agent as module
from memory_agent.memory.predictive_memory_agent import BANK_TOOLS as ADD_TOOLS

TOOL_DESCRIPTION = ('Save the text supplied in content to the knowledge bank. '
    'Your surrounding reply is not saved by this tool. Call it more than once when needed.')
CONTENT_DESCRIPTION = ('The selected information, with the concrete details needed to understand and use it later. '
    'Include the information itself, not just its name or a statement that it was saved. '
    'This may include original text, code, or formulas.')


def test_schema_changes_only_descriptions_and_leaves_shared_add_tools_untouched():
    expected = copy.deepcopy(ADD_TOOLS[0])
    expected['function']['parameters']['additionalProperties'] = False
    expected['function']['description'] = TOOL_DESCRIPTION
    expected['function']['parameters']['properties']['content']['description'] = CONTENT_DESCRIPTION
    assert module.BANK_TOOLS[0] == expected
    assert ADD_TOOLS[0]['function']['description'] != TOOL_DESCRIPTION
    assert set(expected['function']['parameters']['properties']) == {'content'}


def test_real_loop_payload_and_multiple_verbatim_saves():
    bodies = ['原始条件：X 使用全部列；H 使用前两列。\n```python\nX = data[:, :]\nH = X[:, :2]\n```',
              'Formula: y = Xβ + ε\nLiteral tags: <context_for_action>example</context_for_action>\n' * 90]
    agent = module.RemindFirstMemoryAgent(llm=Script(read(), response(
        *(call('memory_add', {'content': text}, f'add-{i}') for i, text in enumerate(bodies)),
        content='<no_intervention/> Selected complete inputs. THIS COMMENT IS NOT SAVED.'), done()))
    result = run(agent)
    assert [op.action for op in result.operations] == ['read', 'add', 'add']
    assert all(op.success for op in result.operations)
    assert [entry['content'] for entry in agent.memory.to_dict()['knowledge']] == bodies
    for request in agent.llm.calls:
        assert [tool['function']['name'] for tool in request['tools']] == ['memory_add','memory_read']
        schema = request['tools'][0]['function']
        assert schema['description'] == TOOL_DESCRIPTION
        assert schema['parameters']['properties']['content']['description'] == CONTENT_DESCRIPTION
    assert all(request['system'] == module.REMIND_FIRST_SYSTEM for request in agent.llm.calls)
    assert not result.should_inject


def test_prompt_guided_source_with_tool_descriptions_normalized():
    source = Path(module.__file__).read_text()
    from test_complete_save_prompt import restore_parent_prompt
    source = restore_parent_prompt(source)
    tree = ast.parse(source)
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
        and ast.unparse(node.targets[0]) in [
            "BANK_TOOLS[0]['function']['description']",
            "BANK_TOOLS[0]['function']['parameters']['properties']['content']['description']"]]
    assert len(assignments) == 2
    lines = source.splitlines(keepends=True)
    for node in reversed(assignments):
        replacement = ('BANK_TOOLS[0]["function"]["description"] = "Save information in the knowledge memory bank."\n'
                       if node is assignments[0] else '')
        lines[node.lineno-1:node.end_lineno] = [replacement]
    assert hashlib.sha256(''.join(lines).encode()).hexdigest() == 'ad21e6fdccf36b6f37e08483b6c281d9d9738e7c8f0fa4602fbfcdf81bf76b2f'
