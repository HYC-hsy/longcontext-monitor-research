"""Approved context-and-bank wording; no runtime/lifecycle changes."""
import hashlib
from pathlib import Path
from memory_agent.memory import read_context_predictive_memory_agent as module
from test_remind_first_loop import make, read, decision, done, run

OLD = "After receiving its result, based on the task agent's current and upcoming work, decide whether to remind it of information in that bank."
NEW = 'After receiving its result, consider both the conversation context and the knowledge bank to decide whether to remind the task agent, and what to remind it of, based on its current and upcoming work.'
PARENT_SOURCE_SHA256 = '335950c22fecde20eaeab9234ee2f74b370cfb010d6498593a9290d9457bc0ca'


def test_only_approved_sentence_changed_from_71fd_parent():
    source = Path(module.__file__).read_text(encoding='utf-8')
    assert source.count(NEW) == 1
    assert OLD not in source
    assert hashlib.sha256(source.replace(NEW, OLD).encode()).hexdigest() == PARENT_SOURCE_SHA256


def test_context_and_bank_wording_reaches_all_requests_and_initialization_is_unified():
    agent = make(read(), decision(), done('Nothing to save.'))
    result = run(agent)
    assert not result.should_inject
    assert [item['stage'] for item in result.loop_rounds] == ['remind', 'remind', 'organize']
    assert all(NEW in request['system'] for request in agent.llm.calls)
    assert all(OLD not in request['system'] for request in agent.llm.calls)
    assert '(empty)' in result.operations[0].content
