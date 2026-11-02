"""Opt-in generation-context consumer; no changes to memory write policy."""
from p1_linked_agent import LinkedSourceP1Agent, SYSTEM as LINKED_SYSTEM

SYSTEM = LINKED_SYSTEM + ("\nWhen selected sources are insufficient to understand an entry, memory_read_source "
    "with view='context' can page its frozen visible generation input. Default view='sources' "
    "returns selected sources. Context is not per-claim evidence; read only when useful.\n")


class ContextSourceP1Agent(LinkedSourceP1Agent):
    system = SYSTEM
    context_views = True

    def get_tools_schema(self):
        tools = super().get_tools_schema()
        tool = tools[-1]['function']
        tool['description'] += ' Optional context view reads a memory/STATUS frozen generation input, not proof.'
        tool['parameters']['properties']['view'] = {
            'type':'string', 'enum':['sources','context'], 'default':'sources'}
        return tools
