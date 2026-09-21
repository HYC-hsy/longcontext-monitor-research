from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MonitorAction:
    kind: str
    payload: dict[str, Any]


@dataclass
class ToolOutcome:
    data: Any
    continue_review: bool = True
    action: MonitorAction | None = None
