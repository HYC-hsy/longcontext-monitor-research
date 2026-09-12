"""No-checker evidence-carrying task state for Stage 6B.

This module is deliberately passive: it maintains state and provenance but
never prompts the Agent, blocks completion, or invokes a verifier/checker.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


CARD_SCHEMA = "evidence-carrying-task-card/0"
OBSERVATION_SCHEMA = "public-state-observation/0"
STATE_SCHEMA = "evidence-carrying-state/0"
PATCH_SCHEMA = "evidence-state-patch/0"
VIEW_SCHEMA = "evidence-state-view/0"

EPISTEMIC_LEVELS = frozenset({
    "unknown", "claimed", "observed", "supported", "contested", "superseded",
})
SOURCE_KINDS = frozenset({
    "agent_claim", "tool_result", "environment_observation", "task_requirement",
})
OBSERVATION_RESULTS = frozenset({"supports", "contradicts", "unknown", "supersedes"})


def _required_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} must be a non-empty string")
    return text


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclasses.dataclass(frozen=True)
class AcceptancePredicate:
    predicate_id: str
    description: str
    observable_by: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AcceptancePredicate":
        sources = tuple(dict.fromkeys(
            _required_text(item, "observable_by") for item in value.get("observable_by", [])
        ))
        if not sources or set(sources) - SOURCE_KINDS:
            raise ValueError("observable_by must name supported public source kinds")
        return cls(
            predicate_id=_required_text(value.get("predicate_id"), "predicate_id"),
            description=_required_text(value.get("description"), "predicate description"),
            observable_by=sources,
        )


@dataclasses.dataclass(frozen=True)
class AtomicCriterion:
    """A source-grounded requirement atom represented by one or more predicates."""

    criterion_id: str
    description: str
    contract_span_ids: tuple[str, ...]
    required_at: tuple[str, ...]
    predicate_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AtomicCriterion":
        spans = tuple(dict.fromkeys(
            _required_text(item, "contract_span_id") for item in value.get("contract_span_ids", [])
        ))
        if not spans or any(len(span) != 5 or span[0] != "L" or not span[1:].isdigit() for span in spans):
            raise ValueError("atomic criterion needs L0001-style contract_span_ids")
        predicates = tuple(dict.fromkeys(
            _required_text(item, "criterion predicate_id") for item in value.get("predicate_ids", [])
        ))
        if not predicates:
            raise ValueError("atomic criterion needs at least one predicate_id")
        return cls(
            criterion_id=_required_text(value.get("criterion_id"), "criterion_id"),
            description=_required_text(value.get("description"), "criterion description"),
            contract_span_ids=spans,
            required_at=tuple(dict.fromkeys(str(item) for item in value.get("required_at", []))),
            predicate_ids=predicates,
        )


@dataclasses.dataclass(frozen=True)
class PublicObservation:
    observation_id: str
    source_event_id: str
    source_kind: str
    obligation_id: str
    predicate_ids: tuple[str, ...]
    result: str
    subject_version: int
    content_ref: str
    observed_at: str

    @classmethod
    def from_envelope(cls, value: Mapping[str, Any]) -> "PublicObservation":
        if value.get("schema_version") != OBSERVATION_SCHEMA:
            raise ValueError("Unsupported public observation schema")
        source_kind = _required_text(value.get("source_kind"), "source_kind")
        if source_kind not in SOURCE_KINDS:
            raise ValueError(f"Unsupported source_kind: {source_kind}")
        result = _required_text(value.get("result"), "result")
        if result not in OBSERVATION_RESULTS:
            raise ValueError(f"Unsupported observation result: {result}")
        predicate_ids = tuple(dict.fromkeys(
            _required_text(item, "predicate_id") for item in value.get("predicate_ids", [])
        ))
        if not predicate_ids:
            raise ValueError("Observation must name at least one predicate")
        subject_version = int(value.get("subject_version", 0))
        if subject_version < 1:
            raise ValueError("subject_version must be >= 1")
        return cls(
            observation_id=_required_text(value.get("observation_id"), "observation_id"),
            source_event_id=_required_text(value.get("source_event_id"), "source_event_id"),
            source_kind=source_kind,
            obligation_id=_required_text(value.get("obligation_id"), "obligation_id"),
            predicate_ids=predicate_ids,
            result=result,
            subject_version=subject_version,
            content_ref=_required_text(value.get("content_ref"), "content_ref"),
            observed_at=str(value.get("observed_at") or datetime.now(timezone.utc).isoformat()),
        )


@dataclasses.dataclass
class PredicateState:
    specification: AcceptancePredicate
    epistemic_status: str = "unknown"
    observation_ids: list[str] = dataclasses.field(default_factory=list)
    source_event_ids: list[str] = dataclasses.field(default_factory=list)
    version_history: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    refinement_parent_id: str | None = None
    introduced_by_event_id: str | None = None


@dataclasses.dataclass
class ObligationState:
    obligation_id: str
    description: str
    requirement_source_pointer: str
    required_at: tuple[str, ...]
    termination_condition: bool
    dependency_ids: tuple[str, ...]
    version: int
    predicates: dict[str, PredicateState]
    atomic_criteria: dict[str, AtomicCriterion] = dataclasses.field(default_factory=dict)


class EvidenceCarryingState:
    """Passive, versioned task state built only from explicit public observations."""

    def __init__(self, task_id: str, obligations: Sequence[ObligationState]):
        self.task_id = _required_text(task_id, "task_id")
        self.obligations = {item.obligation_id: item for item in obligations}
        if not obligations or len(self.obligations) != len(obligations):
            raise ValueError("Task card must contain unique obligations")
        unknown_dependencies = {
            dependency for item in obligations for dependency in item.dependency_ids
            if dependency not in self.obligations
        }
        if unknown_dependencies:
            raise ValueError(f"Unknown obligation dependencies: {sorted(unknown_dependencies)}")
        self.state_version = 1
        self._seen_observations: set[str] = set()
        self._observations: dict[str, PublicObservation] = {}
        self._patches: list[dict[str, Any]] = []
        self._refinements: list[dict[str, Any]] = []

    @classmethod
    def from_card(cls, card: Mapping[str, Any]) -> "EvidenceCarryingState":
        if card.get("schema_version") != CARD_SCHEMA:
            raise ValueError("Unsupported evidence-carrying task card schema")
        obligations = []
        for raw in card.get("obligations", []):
            predicates = [
                AcceptancePredicate.from_dict(item)
                for item in raw.get("acceptance_predicates", [])
            ]
            predicate_map = {item.predicate_id: PredicateState(item) for item in predicates}
            if not predicate_map or len(predicate_map) != len(predicates):
                raise ValueError("Each obligation needs unique acceptance predicates")
            criteria = [
                AtomicCriterion.from_dict(item) for item in raw.get("atomic_criteria", [])
            ]
            criterion_map = {item.criterion_id: item for item in criteria}
            if len(criterion_map) != len(criteria):
                raise ValueError("Each obligation needs unique atomic criteria")
            unknown_criterion_predicates = {
                predicate_id for item in criteria for predicate_id in item.predicate_ids
                if predicate_id not in predicate_map
            }
            if unknown_criterion_predicates:
                raise ValueError(
                    f"Atomic criteria name unknown predicates: {sorted(unknown_criterion_predicates)}"
                )
            obligations.append(ObligationState(
                obligation_id=_required_text(raw.get("obligation_id"), "obligation_id"),
                description=_required_text(raw.get("description"), "obligation description"),
                requirement_source_pointer=_required_text(
                    raw.get("requirement_source_pointer"), "requirement_source_pointer"
                ),
                required_at=tuple(str(item) for item in raw.get("required_at", [])),
                termination_condition=bool(raw.get("termination_condition", False)),
                dependency_ids=tuple(str(item) for item in raw.get("dependency_ids", [])),
                version=int(raw.get("version", 1)),
                predicates=predicate_map,
                atomic_criteria=criterion_map,
            ))
        return cls(_required_text(card.get("task_id"), "task_id"), obligations)

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "EvidenceCarryingState":
        """Restore public checkpoint state without inventing observation bodies."""
        if snapshot.get("schema_version") != STATE_SCHEMA:
            raise ValueError("Unsupported evidence-carrying state snapshot")
        card = {
            "schema_version": CARD_SCHEMA,
            "task_id": snapshot.get("task_id"),
            "obligations": [],
        }
        for raw in snapshot.get("obligations", []):
            card["obligations"].append({
                "obligation_id": raw.get("obligation_id"),
                "description": raw.get("description"),
                "requirement_source_pointer": raw.get("requirement_source_pointer"),
                "required_at": raw.get("required_at", []),
                "termination_condition": raw.get("termination_condition", False),
                "dependency_ids": raw.get("dependency_ids", []),
                "version": raw.get("version", 1),
                "acceptance_predicates": [{
                    "predicate_id": predicate.get("predicate_id"),
                    "description": predicate.get("description"),
                    "observable_by": predicate.get("observable_by", []),
                } for predicate in raw.get("predicates", [])],
                "atomic_criteria": raw.get("atomic_criteria", []),
            })
        state = cls.from_card(card)
        state.state_version = int(snapshot.get("state_version", 1))
        raw_obligations = {
            raw["obligation_id"]: raw for raw in snapshot.get("obligations", [])
        }
        for obligation_id, obligation in state.obligations.items():
            raw_predicates = {
                raw["predicate_id"]: raw
                for raw in raw_obligations[obligation_id].get("predicates", [])
            }
            for predicate_id, predicate in obligation.predicates.items():
                raw = raw_predicates[predicate_id]
                status = str(raw.get("epistemic_status", "unknown"))
                if status not in EPISTEMIC_LEVELS:
                    raise ValueError(f"Unsupported snapshot epistemic status: {status}")
                predicate.epistemic_status = status
                predicate.observation_ids = list(raw.get("observation_ids", []))
                predicate.source_event_ids = list(raw.get("source_event_ids", []))
                predicate.version_history = list(raw.get("version_history", []))
                predicate.refinement_parent_id = raw.get("refinement_parent_id")
                predicate.introduced_by_event_id = raw.get("introduced_by_event_id")
        return state

    @staticmethod
    def _next_status(current: str, observation: PublicObservation) -> str:
        if observation.result == "supersedes":
            return "superseded"
        if observation.result == "contradicts":
            return "contested"
        if observation.result == "unknown":
            return current if current != "unknown" else "unknown"
        if observation.source_kind == "agent_claim":
            return "claimed" if current in {"unknown", "claimed"} else current
        if observation.source_kind == "task_requirement":
            return current
        if current == "contested":
            return "contested"
        if observation.source_kind == "environment_observation":
            return "supported"
        return "observed"

    def apply_observation(self, envelope: Mapping[str, Any]) -> dict[str, Any] | None:
        observation = PublicObservation.from_envelope(envelope)
        if observation.observation_id in self._seen_observations:
            return None
        obligation = self.obligations.get(observation.obligation_id)
        if obligation is None:
            raise ValueError(f"Unknown obligation_id: {observation.obligation_id}")
        if observation.subject_version != obligation.version:
            raise ValueError("Observation subject_version does not match obligation version")
        unknown = set(observation.predicate_ids) - set(obligation.predicates)
        if unknown:
            raise ValueError(f"Observation names unknown predicates: {sorted(unknown)}")
        disallowed = [
            predicate_id for predicate_id in observation.predicate_ids
            if observation.source_kind not in obligation.predicates[predicate_id].specification.observable_by
        ]
        if disallowed:
            raise ValueError(f"Source kind not allowed for predicates: {sorted(disallowed)}")

        changes = []
        for predicate_id in observation.predicate_ids:
            state = obligation.predicates[predicate_id]
            previous = state.epistemic_status
            current = self._next_status(previous, observation)
            state.epistemic_status = current
            state.observation_ids.append(observation.observation_id)
            state.source_event_ids.append(observation.source_event_id)
            changes.append({
                "predicate_id": predicate_id,
                "previous_status": previous,
                "new_status": current,
            })
        self._seen_observations.add(observation.observation_id)
        self._observations[observation.observation_id] = observation
        self.state_version += 1
        patch_body = {
            "schema_version": PATCH_SCHEMA,
            "task_id": self.task_id,
            "state_version": self.state_version,
            "obligation_id": obligation.obligation_id,
            "obligation_version": obligation.version,
            "observation_id": observation.observation_id,
            "source_event_id": observation.source_event_id,
            "source_kind": observation.source_kind,
            "changes": changes,
        }
        patch = dict(patch_body, patch_id=_stable_hash(patch_body))
        self._patches.append(patch)
        return patch

    def apply_observations(self, envelopes: Iterable[Mapping[str, Any]]) -> int:
        return sum(self.apply_observation(item) is not None for item in envelopes)

    def advance_obligation_version(self, obligation_id: str, source_event_id: str) -> dict[str, Any]:
        obligation = self.obligations[obligation_id]
        previous_version = obligation.version
        obligation.version += 1
        changes = []
        for predicate_id, state in obligation.predicates.items():
            previous = state.epistemic_status
            state.version_history.append({
                "subject_version": previous_version,
                "epistemic_status": previous,
                "observation_ids": list(state.observation_ids),
                "source_event_ids": list(state.source_event_ids),
                "superseded_by_event_id": source_event_id,
            })
            state.epistemic_status = "unknown"
            state.observation_ids = []
            state.source_event_ids = []
            changes.append({
                "predicate_id": predicate_id,
                "previous_status": previous,
                "new_status": "unknown",
            })
        self.state_version += 1
        body = {
            "schema_version": PATCH_SCHEMA,
            "task_id": self.task_id,
            "state_version": self.state_version,
            "obligation_id": obligation_id,
            "previous_obligation_version": previous_version,
            "obligation_version": obligation.version,
            "source_event_id": _required_text(source_event_id, "source_event_id"),
            "reason": "SUBJECT_VERSION_ADVANCED",
            "changes": changes,
        }
        patch = dict(body, patch_id=_stable_hash(body))
        self._patches.append(patch)
        return patch

    def introduce_public_requirement(
        self, *, obligation_id: str, predicate_id: str, description: str,
        requirement_source_pointer: str, contract_span_ids: Sequence[str],
        source_event_id: str,
    ) -> dict[str, Any]:
        """Reopen a source-grounded requirement omitted by the compiled state.

        This operation accepts no inferred acceptance rule: the new obligation,
        criterion, and predicate all preserve the same explicit public requirement
        text and begin UNKNOWN.  Public observations must still establish closure.
        """
        obligation_id = _required_text(obligation_id, "obligation_id")
        predicate_id = _required_text(predicate_id, "predicate_id")
        description = _required_text(description, "requirement description")
        source_event_id = _required_text(source_event_id, "source_event_id")
        if obligation_id in self.obligations:
            raise ValueError("Introduced obligation_id already exists")
        predicate = AcceptancePredicate.from_dict({
            "predicate_id": predicate_id,
            "description": description,
            "observable_by": ["tool_result", "environment_observation"],
        })
        criterion = AtomicCriterion.from_dict({
            "criterion_id": f"{obligation_id}-criterion",
            "description": description,
            "contract_span_ids": list(contract_span_ids),
            "required_at": ["before_completion"],
            "predicate_ids": [predicate_id],
        })
        self.obligations[obligation_id] = ObligationState(
            obligation_id=obligation_id,
            description=description,
            requirement_source_pointer=_required_text(
                requirement_source_pointer, "requirement_source_pointer"
            ),
            required_at=("before_completion",),
            termination_condition=True,
            dependency_ids=(),
            version=1,
            predicates={predicate_id: PredicateState(
                specification=predicate, introduced_by_event_id=source_event_id,
            )},
            atomic_criteria={criterion.criterion_id: criterion},
        )
        self.state_version += 1
        body = {
            "schema_version": PATCH_SCHEMA,
            "task_id": self.task_id,
            "state_version": self.state_version,
            "obligation_id": obligation_id,
            "obligation_version": 1,
            "source_event_id": source_event_id,
            "reason": "PUBLIC_REQUIREMENT_REOPENED",
            "new_predicate_id": predicate_id,
            "contract_span_ids": list(criterion.contract_span_ids),
        }
        patch = dict(body, patch_id=_stable_hash(body))
        self._patches.append(patch)
        return patch

    def refine_acceptance_predicate(
        self, obligation_id: str, parent_predicate_id: str,
        predicate: Mapping[str, Any], source_event_id: str,
        counterexample_observation_id: str,
    ) -> dict[str, Any]:
        """Add a counterexample-grounded predicate without rewriting its parent."""
        obligation = self.obligations[obligation_id]
        if parent_predicate_id not in obligation.predicates:
            raise ValueError("Refinement parent predicate is unknown")
        counterexample = self._observations.get(counterexample_observation_id)
        if counterexample is None or counterexample.result != "contradicts":
            raise ValueError("Refinement requires an applied contradictory observation")
        if counterexample.obligation_id != obligation_id:
            raise ValueError("Counterexample belongs to a different obligation")
        specification = AcceptancePredicate.from_dict(predicate)
        if specification.predicate_id in obligation.predicates:
            raise ValueError("Refinement predicate_id already exists")
        obligation.predicates[specification.predicate_id] = PredicateState(
            specification=specification,
            refinement_parent_id=parent_predicate_id,
            introduced_by_event_id=_required_text(source_event_id, "source_event_id"),
        )
        self.state_version += 1
        body = {
            "schema_version": PATCH_SCHEMA,
            "task_id": self.task_id,
            "state_version": self.state_version,
            "obligation_id": obligation_id,
            "obligation_version": obligation.version,
            "source_event_id": source_event_id,
            "reason": "COUNTEREXAMPLE_GUIDED_REFINEMENT",
            "counterexample_observation_id": counterexample_observation_id,
            "parent_predicate_id": parent_predicate_id,
            "new_predicate_id": specification.predicate_id,
        }
        patch = dict(body, patch_id=_stable_hash(body))
        self._patches.append(patch)
        self._refinements.append({
            "parent_predicate_id": parent_predicate_id,
            "new_predicate_id": specification.predicate_id,
            "source_event_id": source_event_id,
            "counterexample_observation_id": counterexample_observation_id,
        })
        return patch

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": STATE_SCHEMA,
            "task_id": self.task_id,
            "state_version": self.state_version,
            "obligations": [{
                "obligation_id": item.obligation_id,
                "description": item.description,
                "requirement_source_pointer": item.requirement_source_pointer,
                "required_at": list(item.required_at),
                "termination_condition": item.termination_condition,
                "dependency_ids": list(item.dependency_ids),
                "version": item.version,
                "atomic_criteria": [dataclasses.asdict(criterion) for criterion in item.atomic_criteria.values()],
                "predicates": [{
                    "predicate_id": predicate_id,
                    "description": state.specification.description,
                    "observable_by": list(state.specification.observable_by),
                    "epistemic_status": state.epistemic_status,
                    "observation_ids": list(state.observation_ids),
                    "source_event_ids": list(state.source_event_ids),
                    "version_history": list(state.version_history),
                    "refinement_parent_id": state.refinement_parent_id,
                    "introduced_by_event_id": state.introduced_by_event_id,
                } for predicate_id, state in item.predicates.items()],
            } for item in self.obligations.values()],
            "patch_ids": [item["patch_id"] for item in self._patches],
            "refinements": list(self._refinements),
        }

    def patches(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._patches]

    def policy_view(self, *, required_at: str | None = None,
                    max_chars: int = 4000) -> dict[str, Any]:
        """Return a deterministic budgeted view without discarding the ledger.

        Terminal obligations and epistemically risky predicates are prioritized.
        The view is passive and does not choose a recovery action.
        """
        if max_chars < 128:
            raise ValueError("max_chars must be >= 128")
        candidates = []
        status_priority = {
            "contested": 0, "unknown": 1, "claimed": 2,
            "observed": 3, "supported": 4, "superseded": 5,
        }
        for order, obligation in enumerate(self.obligations.values()):
            statuses = [state.epistemic_status for state in obligation.predicates.values()]
            due = required_at is None or required_at in obligation.required_at
            priority = (
                0 if obligation.termination_condition else 1,
                0 if due else 1,
                min(status_priority[item] for item in statuses),
                order,
            )
            candidates.append((priority, obligation, statuses))
        candidates.sort(key=lambda item: item[0])

        selected = []
        omitted_ids = []
        used_chars = 0
        for _, obligation, statuses in candidates:
            row = {
                "obligation_id": obligation.obligation_id,
                "description": obligation.description,
                "required_at": list(obligation.required_at),
                "termination_condition": obligation.termination_condition,
                "version": obligation.version,
                "atomic_criteria": [dataclasses.asdict(criterion) for criterion in obligation.atomic_criteria.values()],
                "predicates": [{
                    "predicate_id": predicate_id,
                    "description": state.specification.description,
                    "epistemic_status": state.epistemic_status,
                    "source_event_ids": list(state.source_event_ids),
                } for predicate_id, state in obligation.predicates.items()],
                "source_event_ids": sorted({
                    event_id for state in obligation.predicates.values()
                    for event_id in state.source_event_ids
                }),
            }
            row_chars = len(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            must_include = obligation.termination_condition
            if selected and used_chars + row_chars > max_chars and not must_include:
                omitted_ids.append(obligation.obligation_id)
                continue
            selected.append(row)
            used_chars += row_chars
        return {
            "schema_version": VIEW_SCHEMA,
            "task_id": self.task_id,
            "state_version": self.state_version,
            "required_at": required_at,
            "max_chars": max_chars,
            "used_chars": used_chars,
            "within_budget": used_chars <= max_chars,
            "obligations": selected,
            "omitted_obligation_ids": omitted_ids,
            "complete": not omitted_ids,
        }
