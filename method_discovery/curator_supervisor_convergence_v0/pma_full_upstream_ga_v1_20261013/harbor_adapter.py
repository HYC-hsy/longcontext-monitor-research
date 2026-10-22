"""Pilot-only forwarding overlay for a byte-pinned existing Harbor GA adapter.

Loaded only by an explicitly selected research --agent path.  The ordinary
adapter, A condition and other experiments do not import this module.
"""

import hashlib
import os
from pathlib import Path

from adapters import harbor_ga_agent as original
from .networked_transport_setup import start_networked_transport


EXPECTED_ADAPTER_SHA256 = "82ac43f2c791bc4d8510e1d851ef7b2c5bead8cdfbb847be36c7ae244821ecce"
EXPECTED_STATEFUL_DIAGNOSTIC_ADAPTER_SHA256 = (
    "8a4513c6b28befe747d581d22e94cd2715f20234c63115e0ea424a56d033c3a0")
FORWARD = (
    "GA_EXPERIMENT_TASK_TURNS",
    "GA_STATEFUL_MEMORY_ENABLED",
    "GA_STATEFUL_MEMORY_MODE",
    "GA_STATEFUL_UNCAPPED_TOTAL",
    "GA_STATEFUL_AGENT_TIME_PROTOCOL",
    "GA_STATEFUL_NATIVE_CONTEXT_POLICY",
    "GA_STATEFUL_RESEARCH_CAPTURE_POLICY",
    "GA_STATEFUL_LIVE_AUTHORIZED",
    "GA_STATEFUL_REQUESTS",
    "GA_STATEFUL_RESPONSES",
    "GA_PMA_UPSTREAM_ENABLED",
    "GA_PMA_UPSTREAM_REQUESTS",
    "GA_PMA_UPSTREAM_RESPONSES",
    "GA_PMA_UPSTREAM_CANDIDATE",
    "GA_PMA_UPSTREAM_DEADLINE_EPOCH",
    "GA_PMA_CAPTURE_TASK_REQUESTS",
    "GA_POS_ENABLED",
    "GA_POS_CITATION_FIXED",
    "GA_POS_PMA_COMPLEMENT",
    "GA_POS_PMA_SHARED_VIEW",
    "GA_POS_TRANSPORT",
    "GA_POS_WORKER_SCRIPT",
    "GA_POS_VENDOR_ROOT",
    "GA_POS_EPISODE_MODULE",
    "GA_POS_ARCHIVE",
    "GA_POS_FAKE_REPLIES",
    "GA_POS_PROFILE_FILE",
    "GA_POS_PROFILE_NAME",
    "GA_POS_BINDING_FILE",
    "GA_POS_LIVE_AUTHORIZED",
    "GA_POS_TIMEOUT",
    "GA_POS_DEADLINE_EPOCH",
    "GA_TASK_COMPLETE_RESPONSE",
    "GA_TASK_DEADLINE_EPOCH",
)

actual = hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest()
if actual != EXPECTED_ADAPTER_SHA256 and not (
        os.environ.get('GA_STATEFUL_MEMORY_ENABLED') == '1' and
        os.environ.get('GA_STATEFUL_AGENT_TIME_PROTOCOL') == 'diagnostic-uncapped-v1' and
        actual == EXPECTED_STATEFUL_DIAGNOSTIC_ADAPTER_SHA256):
    raise RuntimeError("PMA Harbor base adapter byte identity mismatch")
if any(name in original.FORWARDED_ENV_VARS for name in FORWARD):
    raise RuntimeError("PMA Harbor forwarding unexpectedly already present")
# This explicit research adapter is loaded in its own Harbor subprocess. The
# original run method reads this tuple; remove keys independently of network
# mode, without editing the external installed adapter or task profiles.
original.FORWARDED_ENV_VARS = tuple(
    name for name in original.FORWARDED_ENV_VARS if not name.endswith("_API_KEY")
) + FORWARD


class HarborGenericAgent(original.HarborGenericAgent):
    """Same original run/setup implementation, with only four extra env names."""

    @staticmethod
    def name() -> str:
        return "generic-agent-harbor-pma-upstream"

    async def setup(self, environment) -> None:
        await super().setup(environment)
        if __import__("os").environ.get("GA_RUN_ISOLATION") == "networked-host-keyed-v1":
            python_bin, _ = original._runtime_paths(self.python_home)
            await start_networked_transport(environment, python_bin, original.CONTAINER_GA)

    async def run(self, instruction, environment, context) -> None:
        if os.environ.get('GA_STATEFUL_AGENT_TIME_PROTOCOL') == 'diagnostic-uncapped-v1':
            if (os.environ.get('GA_STATEFUL_MEMORY_ENABLED') != '1' or
                    self.condition_id != 'stateful-memory-v1'):
                raise RuntimeError('uncapped diagnostic requires stateful identity')
            # The pinned base adapter now supports an uncapped wrapper natively.
            # Do not also apply the historical string-rewriting overlay.
            self.timeout_sec = None
        try:
            await super().run(instruction, environment, context)
        except RuntimeError as exc:
            metadata = getattr(context, 'metadata', None)
            if (str(exc).startswith('GenericAgent did not complete one task turn:') and
                    isinstance(metadata, dict) and
                    metadata.get('run_id') == self.run_id and
                    metadata.get('archive_status') == 'failed' and
                    isinstance(metadata.get('wrapper_return_code'), int) and
                    metadata['wrapper_return_code'] != 0):
                from harbor.agents.installed.base import NonZeroAgentExitCodeError
                raise NonZeroAgentExitCodeError(str(exc)) from exc
            raise


class _UncappedAgentExecution:
    """Candidate-only overlay for the pinned GA adapter's one long exec.

    The base adapter's setup, environment, metadata, and failure handling remain
    unchanged. Only its cumulative shell loop and exec timeout are removed.
    """

    def __init__(self, environment, run_id, base_timeout):
        self._environment = environment
        self._run_id = run_id
        self._base_timeout = base_timeout
        self.long_exec_seen = False

    def __getattr__(self, name):
        return getattr(self._environment, name)

    async def exec(self, command, *args, **kwargs):
        marker = f'# GA_WRAPPER_RUN_ID={self._run_id}\n'
        if marker in command:
            if self.long_exec_seen:
                raise RuntimeError('stateful agent long exec repeated')
            count = max(1, self._base_timeout // 2)
            old = f'timed_out=1\nfor i in $(seq 1 {count}); do'
            if command.count(marker) != 1 or command.count(old) != 1 or (
                    kwargs.get('timeout_sec') != self._base_timeout + 90):
                raise RuntimeError('pinned GA adapter timeout template changed')
            command = command.replace(old, 'timed_out=0\nwhile :; do')
            kwargs['timeout_sec'] = None
            self.long_exec_seen = True
        return await self._environment.exec(command, *args, **kwargs)

