from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from types import SimpleNamespace


class _BaseAgent:
    pass


for name in (
    "harbor",
    "harbor.agents",
    "harbor.environments",
    "harbor.models",
    "harbor.models.agent",
):
    sys.modules.setdefault(name, ModuleType(name))
base_module = ModuleType("harbor.agents.base")
base_module.BaseAgent = _BaseAgent
environment_module = ModuleType("harbor.environments.base")
environment_module.BaseEnvironment = object
context_module = ModuleType("harbor.models.agent.context")
context_module.AgentContext = object
sys.modules.setdefault("harbor.agents.base", base_module)
sys.modules.setdefault("harbor.environments.base", environment_module)
sys.modules.setdefault("harbor.models.agent.context", context_module)

from adapters.harbor_ga_clawbench import HarborClawBenchGenericAgent


def test_clawbench_bootstrap_creates_initial_cdp_tab() -> None:
    calls = []

    class Environment:
        async def exec(self, command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(
                return_code=0,
                stdout='{"id":"tab-1","url":"http://127.0.0.1:7878/submit"}',
                stderr="",
            )

    agent = object.__new__(HarborClawBenchGenericAgent)
    asyncio.run(agent._bootstrap_browser(Environment()))
    assert "/json/new?http://127.0.0.1:7878/submit" in calls[0][0]
    assert calls[0][1]["timeout_sec"] == 120
    assert agent.browser_bootstrap == {
        "cdp_tab_created": True,
        "tab_id": "tab-1",
        "initial_url": "http://127.0.0.1:7878/submit",
    }
