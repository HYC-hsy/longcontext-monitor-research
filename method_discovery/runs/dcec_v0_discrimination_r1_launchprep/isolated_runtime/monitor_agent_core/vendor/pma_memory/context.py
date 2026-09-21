# Verbatim context methods from PMA memory_enabled_agent.py; see NOTICE.
class AuthorContext:
    def _get_memory_agent_context(self) -> str:
        """Build context for the memory agent: task description + sliding window.

        The memory agent acts as selective attention — it always sees:
        1. The original task description (for grounding in requirements)
        2. A sliding window of the last N steps (recent behavior)
        The memory BANK provides long-term context beyond the window.
        """
        parts = []

        # Always include task description
        if self._task_description:
            parts.append(f"[Task Description]\n{self._task_description}")

        # Sliding window of recent steps (skip first entry which is task description,
        # already included above via [Task Description] section)
        window = self._accumulated_observations[1:][-self._sliding_window_size:]
        if window:
            parts.append("[Recent Trajectory (last {} steps)]".format(len(window)))
            for entry in window:
                parts.append(self._format_step_entry(entry))

        return "\n\n".join(parts)

    @staticmethod
    def _format_step_entry(entry: dict) -> str:
        step = entry["step"]
        sections = [f"[Step {step}]"]

        if entry.get("analysis"):
            sections.append(f"Agent Analysis: {entry['analysis']}")

        if entry.get("plan"):
            sections.append(f"Agent Plan: {entry['plan']}")

        if entry.get("commands"):
            cmds = entry["commands"][:5]
            cmd_str = "; ".join(cmds)
            if len(entry["commands"]) > 5:
                cmd_str += f" (+{len(entry['commands']) - 5} more)"
            sections.append(f"Commands Executed: {cmd_str}")

        obs = entry.get("observation", "")
        # observation is already truncated to ~10KB by Terminus2._limit_output_length
        # Pass it through unchanged so memory agent sees exactly what action agent saw
        sections.append(f"Terminal Output: {obs}")

        return "\n".join(sections)
