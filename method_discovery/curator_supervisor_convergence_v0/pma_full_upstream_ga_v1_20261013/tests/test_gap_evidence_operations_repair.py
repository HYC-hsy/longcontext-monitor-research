"""Deterministic operation-isolation and stable identity contracts; no provider."""
import unittest
from unittest.mock import patch

from evidence_gap_agent import EvidenceGapMemoryAgent
from evidence_gap_store import EvidenceGapMemory
from test_gap_evidence_agent import RAW, blocks, reply


class OperationRepairTests(unittest.TestCase):
    def prepared(self, bank=None):
        bank = EvidenceGapMemory() if bank is None else bank
        agent = EvidenceGapMemoryAgent(task="task", memory=bank)
        agent.prepare_visible_context(RAW, blocks())
        prompt = agent._build_phase1_prompt(RAW, 1)
        self.assertIsNotNone(agent._parts)
        self.evidence = [{"source": next(k for k, v in agent._parts.catalog.items()
                          if v.snapshot.record.role == "tool_observation"),
                          "quote": "check passed"}]
        return agent, bank, prompt

    def test_memory_has_one_display_identity(self):
        bank = EvidenceGapMemory()
        key = bank.save_gap("old observation")
        agent, bank, prompt = self.prepared(bank)
        visible = agent._parts.catalog[key]
        self.assertIn(f"[{key} memory_derived", prompt)
        self.assertNotIn(visible.snapshot.record.handle, prompt)
        self.assertNotIn(visible.snapshot.record.handle, agent._parts.catalog)
        self.assertEqual(visible.snapshot.record.parent_revision_id,
                         agent._draft.active_revisions[key])
