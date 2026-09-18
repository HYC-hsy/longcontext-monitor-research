"""Bounded, independent local verification for one concrete question.

This module is deliberately not wired into MonitorAgent.review().  A probe owns
an independent provider client and a restricted dispatch surface; it returns a
local result to its caller and cannot intervene, wait, or approve completion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from .actions import MonitorAction, ToolOutcome
from .loop import MonitorLoopError, run_review
from .provider import MonitorProviderClient


ProbeMode = Literal["direct", "expectation_first"]


class ProbeBudgetExceeded(RuntimeError):
    """The probe reached its explicit request budget."""


@dataclass(frozen=True)
class ProbeConfig:
    mode: ProbeMode = "direct"
    source_paths: tuple[str, ...] = ("task/original_task.txt",)
    evidence_paths: tuple[str, ...] = ()
    max_requests: int = 4
    max_turns: int = 8
    allow_code_run: bool = False


@dataclass
class ProbeResult:
    mode: ProbeMode
    status: str = "incomplete"
    outcome: str | None = None
    expectation: str | None = None
    expectation_revision: str | None = None
    conclusion: str | None = None
    phases: list[str] = field(default_factory=list)
    requests: int = 0
    limitation: str | None = None
    history_before: dict[str, Any] | None = None
    history_after: dict[str, Any] | None = None


def score_local_result(result: ProbeResult, expected: str) -> dict[str, bool | None]:
    """Only an explicit finished verdict is eligible for correctness scoring."""
    completed = result.status == "completed"
    return {
        "score_eligible": completed,
        "correct": (result.outcome == expected) if completed else None,
    }


def _tool(name: str, description: str, properties: dict[str, Any],
          required: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": list(required)},
    }}


class IndependentVerifier:
    """Run a bounded probe without sharing parent history or control actions.

    ``client`` must be a newly-created provider client.  The class never copies
    or mutates a parent MonitorAgent client.  ``code_runner`` is optional and is
    intentionally disabled unless the caller opts in explicitly.
    """

    def __init__(self, client: MonitorProviderClient, workspace, config: ProbeConfig,
                 code_runner: Callable[[dict[str, Any]], Any] | None = None,
                 audit: Callable[..., None] | None = None):
        if config.mode not in ("direct", "expectation_first"):
            raise ValueError("mode must be direct or expectation_first")
        if config.max_requests < 1 or config.max_turns < 1:
            raise ValueError("probe budgets must be positive")
        if config.allow_code_run and code_runner is None:
            raise ValueError("allow_code_run requires code_runner")
        self.client = client
        self.workspace = workspace
        self.config = config
        self.code_runner = code_runner
        self.audit = audit
        self._requests = 0
        self._allowed: set[str] = set()
        self.evidence_refs: list[dict[str, Any]] = []
        self._original_complete = None

    @property
    def logical_calls(self) -> int:
        """Number of client.complete calls attempted, including a failed call."""
        return self._requests

    @classmethod
    def from_provider_config(cls, config_name: str, provider_config: dict[str, Any],
                             workspace, config: ProbeConfig, **kwargs):
        """Create a fresh client; no history or active-context callback is copied."""
        client = MonitorProviderClient(config_name + "::independent_probe", provider_config)
        return cls(client, workspace, config, **kwargs)

    def _record(self, event: str, **fields):
        if self.audit is not None:
            self.audit(event, **fields)

    def _allowed_path(self, path: str) -> bool:
        return str(path).replace("\\", "/") in self._allowed

    def _dispatch(self, name: str, arguments: dict[str, Any], phase: str) -> ToolOutcome:
        if name == "file_read":
            path = str(arguments.get("path", "")).replace("\\", "/")
            if not self._allowed_path(path):
                return ToolOutcome({"status": "error", "error": "path is outside this probe phase"})
            data = self.workspace.read_text(
                path, arguments.get("start", 1), arguments.get("count", 200),
                tail=arguments.get("tail", False), offset=arguments.get("offset", 0),
                max_chars=arguments.get("max_chars", 20000),
            )
            self.evidence_refs.append({
                key: data.get(key) for key in
                ("path", "start", "lines", "offset", "sha256", "truncated", "next_read")
                if key in data
            })
            return ToolOutcome(data)
        if name == "code_run":
            if phase != "evidence" or not self.config.allow_code_run:
                return ToolOutcome({"status": "error", "error": "code_run is unavailable in this probe phase"})
            return ToolOutcome(self.code_runner(arguments))
        if name == "commit_expectation" and phase == "expectation":
            content = str(arguments.get("expectation", "")).strip()
            if not content:
                return ToolOutcome({"status": "error", "error": "expectation must not be empty"})
            return ToolOutcome(None, action=MonitorAction(
                "probe_phase_complete", {"phase": phase, "expectation": content}))
        if name == "finish_probe":
            outcome = arguments.get("outcome")
            if outcome not in {"supported_in_scope", "contradicted", "unresolved"}:
                return ToolOutcome({"status": "error", "error": "explicit local outcome is required"})
            conclusion = arguments.get("conclusion")
            if not isinstance(conclusion, str) or not conclusion.strip():
                return ToolOutcome({"status": "error", "error": "a substantive conclusion is required"})
            return ToolOutcome(None, action=MonitorAction(
                "probe_complete", {"phase": phase, "outcome": outcome,
                                    "conclusion": conclusion.strip(),
                                    "revised_expectation": str(
                                        arguments.get("revised_expectation", "")).strip()}))
        return ToolOutcome({"status": "error", "error": f"tool {name} is not available in a probe"})

    def _tools(self, phase: str) -> list[dict[str, Any]]:
        tools = [_tool("file_read", "Read one permitted source or evidence file.", {
            "path": {"type": "string"}, "start": {"type": "integer"},
            "count": {"type": "integer"}, "tail": {"type": "boolean"},
            "offset": {"type": "integer", "minimum": 0,
                       "description": "Use the offset returned in next_read to continue a truncated first line."},
            "max_chars": {"type": "integer", "minimum": 1, "maximum": 200000,
                          "description": "Maximum decoded characters to return; normally omit."},
        })]
        if self.config.allow_code_run and phase == "evidence":
            tools.append(_tool("code_run", "Run one caller-supplied bounded observation.", {
                "code": {"type": "string"}, "type": {"type": "string"},
                "timeout": {"type": "integer"},
            }))
        if phase == "expectation":
            tools.append(_tool("commit_expectation", "Commit the expected observable behavior.", {
                "expectation": {"type": "string"},
            }, ("expectation",)))
        else:
            tools.append(_tool(
                "finish_probe",
                "Return the scoped verdict: supported_in_scope when evidence supports the claim; "
                "contradicted when evidence shows a concrete mismatch; unresolved when evidence "
                "cannot decide. Put reasoning in conclusion, not outcome.",
                {
                "outcome": {"type": "string", "enum": [
                    "supported_in_scope", "contradicted", "unresolved"]},
                "conclusion": {"type": "string"},
                "revised_expectation": {"type": "string"},
            }, ("outcome", "conclusion")))
        return tools

    def _phase(self, phase: str, prompt: str, paths: tuple[str, ...]) -> MonitorAction:
        self._allowed = {str(path).replace("\\", "/") for path in paths}
        visible_prompt = (
            f"{prompt}\n\nPermitted files in this phase:\n"
            + "\n".join(f"- {path}" for path in paths)
            + "\nRead what is needed before making the local judgment."
        )
        system = (
            "You are a temporary local verifier. Answer only the concrete question in scope. "
            "Use the permitted read tool and finish with the phase action. Do not infer whole-task "
            "completion. A local conclusion may remain unresolved. "
        )
        if phase == "expectation":
            system += (
                "You can see requirements and necessary background, but not implementation "
                "or execution evidence. Do not decide whether the actual implementation works. "
                "Commit what a correct implementation should observably do, including a check "
                "that could distinguish it from a superficial implementation."
            )
        else:
            system += (
                "Compare the committed expectation (if any) with permitted implementation and "
                "execution evidence. If the expectation itself was mistaken, record a corrected "
                "one in revised_expectation and explain the revision; do not treat either as an oracle."
            )
        self._record("probe_phase_started", phase=phase, paths=list(paths))
        try:
            action = run_review(
                self.client, system, visible_prompt, self._tools(phase),
                lambda name, args: self._dispatch(name, args, phase),
                max_turns=self.config.max_turns, audit=self._record,
            )
        except ProbeBudgetExceeded:
            return MonitorAction("probe_budget_exhausted", {"phase": phase})
        except MonitorLoopError:
            return MonitorAction("probe_turn_limit", {"phase": phase})
        self._record("probe_phase_finished", phase=phase, action=action.kind)
        return action

    def _complete_request(self, messages, tools):
        if self._requests >= self.config.max_requests:
            raise ProbeBudgetExceeded("probe request budget exhausted")
        self._requests += 1
        return self._original_complete(messages, tools)

    def run(self, question: str) -> ProbeResult:
        result = ProbeResult(self.config.mode)
        result.history_before = self.client.history_measure()
        original_complete = self.client.complete
        self._original_complete = original_complete
        self.client.complete = self._complete_request
        try:
            if self.config.mode == "direct":
                action = self._phase("evidence", question, self.config.source_paths + self.config.evidence_paths)
                result.phases.append("evidence")
                if action.kind == "probe_complete":
                    result.status = "completed"
                    result.outcome = action.payload["outcome"]
                    result.conclusion = action.payload.get("conclusion")
                    result.expectation_revision = action.payload.get("revised_expectation") or None
                else:
                    result.status = action.kind
                    result.limitation = action.kind
            else:
                action = self._phase("expectation", question, self.config.source_paths)
                result.phases.append("expectation")
                if action.kind != "probe_phase_complete":
                    result.status = action.kind
                    result.limitation = action.kind
                    return result
                result.expectation = action.payload["expectation"]
                evidence_prompt = (
                    f"Original question:\n{question}\n\nCommitted expectation:\n{result.expectation}\n\n"
                    "Now inspect the implementation and execution evidence and decide only whether the "
                    "expectation is supported, contradicted, or unresolved in this scope."
                )
                action = self._phase("evidence", evidence_prompt,
                                     self.config.source_paths + self.config.evidence_paths)
                result.phases.append("evidence")
                if action.kind == "probe_complete":
                    result.status = "completed"
                    result.outcome = action.payload["outcome"]
                    result.conclusion = action.payload.get("conclusion")
                    result.expectation_revision = action.payload.get("revised_expectation") or None
                else:
                    result.status = action.kind
                    result.limitation = action.kind
        finally:
            self.client.complete = original_complete
            self._original_complete = None
            result.requests = self._requests
            result.history_after = self.client.history_measure()
        return result
