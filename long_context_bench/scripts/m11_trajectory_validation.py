"""Shared validity checks for M11 Natural GenericAgent outputs."""

from __future__ import annotations


def fatal_agent_output(text: str) -> bool:
    """Return true when GA ended after an infrastructure error without tool work."""
    return "!!!Error:" in text and "🛠️ Tool:" not in text


def terminal_agent_error(text: str) -> bool:
    """Return true when the final GA turn ended in a provider/API error."""
    marker = text.rfind("!!!Error:")
    if marker < 0:
        return False
    tail = text[marker:]
    # A later normal turn makes this an earlier recoverable error. At a
    # terminal provider failure only the error and round sentinel follow.
    return "**Turn " not in tail[len("!!!Error:"):] and "[ROUND END]" in tail


__all__ = ["fatal_agent_output", "terminal_agent_error"]
