"""Gated maintenance with the unchanged shared phase-2 tag selector."""
from citation_gate_agent import CitationGateMemoryAgent
from verbatim_selection_mixin import VerbatimSelectionMixin


class VerbatimSelectionCitationGateAgent(VerbatimSelectionMixin, CitationGateMemoryAgent):
    """Existing gated reviewer and bank, with a strict phase-2 tag protocol."""
