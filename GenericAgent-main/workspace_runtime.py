"""Resolve the Agent tool workspace independently from task protocol I/O."""
from __future__ import annotations

import os
import time


def resolve_workspace_dir(task_dir: str | None, configured: str | None = None) -> str:
    """Return an existing directory; preserve legacy behavior when unset."""
    fallback = task_dir or os.path.join(os.path.dirname(__file__), "temp")
    candidate = configured if configured is not None else os.environ.get("GA_TASK_WORKSPACE_DIR")
    if not candidate:
        return os.path.realpath(fallback)
    if not os.path.isabs(candidate):
        raise ValueError("GA_TASK_WORKSPACE_DIR must be an absolute path")
    resolved = os.path.realpath(candidate)
    if not os.path.isdir(resolved):
        raise ValueError(f"GA_TASK_WORKSPACE_DIR is not an existing directory: {resolved}")
    return resolved


def prepare_task_query(raw_query: str, task_dir: str | None, *, inline_long: bool) -> str:
    """Preserve benchmark instructions inline; retain legacy spill behavior otherwise."""
    if len(raw_query) <= 2000 or inline_long:
        return raw_query
    destination = task_dir or os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(destination, exist_ok=True)
    task_file = os.path.join(destination, f"user_prompt_{int(time.time())}.md")
    with open(task_file, "w", encoding="utf-8") as stream:
        stream.write(raw_query)
    return f"Long user prompt saved to {task_file}. Read and execute."


def workspace_contract(workspace_dir: str) -> str:
    return (
        "\n[Task Workspace - authoritative]\n"
        f"The only task repository and delivery workspace is: {workspace_dir}\n"
        "Use this directory as cwd for all relative tool operations. Work directly in it. "
        "Do not clone, copy, or create a substitute repository elsewhere. "
        "The native verifier evaluates only this workspace.\n"
    )
