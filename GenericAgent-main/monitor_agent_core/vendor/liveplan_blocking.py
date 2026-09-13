"""Extracted verbatim method from LivePlan plan_monitor/phases.py.

Source: Intelligent-CAT-Lab/Agent-Planner
Commit: c16797a09b964f901b34fe3da430ee011a5cc660 (MIT).
Only the enclosing class is replaced; see bundled LivePlan license.
This is the blocking predicate, NOT the author's complete scheduler.
"""


class BlockingDecision:
    def __init__(self, rule_matches):
        self.rule_matches = rule_matches

    def should_block_and_refine(self) -> bool:
        """
        Check if any triggered rules require BLOCKING execution and calling refiner.

        This is for rules (plan_compliance, dwell_times, oscillations) with block_execution=True
        that should prevent the current action from being executed or added to history.

        Other rules (phase_transitions, strategy_shifts) still trigger refiner but allow
        execution to proceed normally (post-hoc refinement).

        Returns:
            True if any rule_match has block_execution=True, False otherwise
        """
        for match in self.rule_matches:
            if hasattr(match, 'block_execution') and match.block_execution:
                return True
        return False
