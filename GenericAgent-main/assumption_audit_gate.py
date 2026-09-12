"""M3 assumption audit with M2-on-UNKNOWN before evidence-gated completion."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from completion_contract import CompletionContract, TerminalGuard
from online_evidence_gate import OnlineEvidenceCompletionGate, inert_json_tool
from research_runtime import CompletionDecision, emit


NORMATIVE = re.compile(
    r"\b(must|shall|should|required|requirement|ensure|implement|support|accept|return|"
    r"include|exclude|never|always|exactly|before|after|without|do not|don't)\b",
    re.IGNORECASE,
)


def extract_public_instruction(text: str) -> str:
    """Use the same public-instruction boundary as the Stage 6B compiler."""
    marker = "## Prompt"
    if marker not in text:
        return text.strip()
    public = text.split(marker, 1)[1]
    boundaries = [
        public.find(item) for item in ("## Expected Behavior", "## Grading Criteria")
        if public.find(item) >= 0
    ]
    if boundaries:
        public = public[:min(boundaries)]
    return public.strip()


def _json_object(raw: str) -> Mapping[str, Any]:
    text = raw.strip().lstrip("\ufeff\u200b")
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.I | re.S)
    if fenced:
        text = fenced.group(1)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(value, Mapping):
        raise ValueError("Representation audit response must be an object")
    return value


class AssumptionAuditCompletionGate(OnlineEvidenceCompletionGate):
    """Repair public-state omissions once, then reuse the ordinary Stage 6D gate."""

    def __init__(self, *args, disposition_card: Mapping[str, Any],
                 public_task_text: str, audit_config: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.disposition_card = dict(disposition_card)
        self.public_task_text = public_task_text
        self.audit_config = audit_config or self.config_name
        self._audit_complete = False
        self._audit_calls = 0
        self._audit_rows: list[dict[str, Any]] = []

    def _source_lines(self) -> dict[str, str]:
        return {
            f"L{index:04d}": line
            for index, line in enumerate(extract_public_instruction(self.public_task_text).splitlines(), 1)
            if line.strip()
        }

    def _criteria(self) -> dict[str, str]:
        return {
            criterion.criterion_id: criterion.description
            for obligation in self.state.obligations.values()
            for criterion in obligation.atomic_criteria.values()
        }

    def _cases(self) -> list[dict[str, Any]]:
        lines, criteria = self._source_lines(), self._criteria()
        cases = []
        for index, row in enumerate(self.disposition_card.get("source_dispositions", []), 1):
            atom_ids = [str(item) for item in row.get("source_atom_ids", []) if str(item) in lines]
            if not atom_ids:
                continue
            text = "\n".join(lines[item] for item in atom_ids)
            disposition = str(row.get("disposition", "unknown"))
            if disposition not in {"required", "unknown"} and not NORMATIVE.search(text):
                continue
            linked = [str(item) for item in row.get("criterion_ids", []) if str(item) in criteria]
            cases.append({
                "case_id": f"D{index:04d}", "source_atom_ids": atom_ids,
                "source_text": text, "current_disposition": disposition,
                "linked_criterion_ids": linked,
            })
        return cases

    def _call_audit(self, prompt: str) -> Mapping[str, Any]:
        from llmcore import resolve_session

        session = resolve_session(self.audit_config)
        if session is None:
            raise ValueError(f"Unsupported representation audit config: {self.audit_config}")
        session.max_tokens = 12000
        session.tools = inert_json_tool(
            getattr(session, "api_mode", "messages"), "record_audit_error"
        )
        raw = "".join(session.raw_ask([{
            "role": "user", "content": [{"type": "text", "text": prompt}],
        }])).strip()
        if not raw or raw.startswith("!!!Error:"):
            raise RuntimeError(f"Representation audit failed: {raw[:300] or '<empty>'}")
        self._audit_calls += 1
        return _json_object(raw)

    def _m3_prompt(self, cases: list[Mapping[str, Any]]) -> str:
        public = {"represented_criteria": self._criteria(), "cases": cases}
        return """Audit whether a compiled task state preserves each PUBLIC source requirement.
Use no checker, hidden test, gold answer, or unstated task fact. A source line is normative only
when its own language imposes behavior; examples, headings, and background may be context.
For each case, decide whether the represented criteria cover its explicit behavior without any
extra premise. Common practice, file type, purpose, and typical implementation are not support.
Return JSON only:
{"method":"m3_assumption_audit","results":[{"case_id":"...","target_kind":"normative|context|uncertain","coverage_without_extra_assumptions":"yes|no|unknown","assumptions":[{"text":"...","status":"supported|unsupported|uncertain","support_criterion_ids":["..."]}],"coverage_reason":"..."}]}
PUBLIC INPUT:
""" + json.dumps(public, ensure_ascii=False)

    def _m2_prompt(self, cases: list[Mapping[str, Any]]) -> str:
        public = {"represented_criteria": self._criteria(), "cases": cases}
        return """Resolve only UNKNOWN results from a public task-state coverage audit.
Use no checker, hidden test, gold answer, or unstated fact. For each normative source behavior,
try to construct a concrete behavior satisfying the represented criteria while violating it.
Failure to imagine one is UNKNOWN, not entailment. Return JSON only:
{"method":"m2_directed_counterexample","results":[{"case_id":"...","target_kind":"normative|context|uncertain","coverage_status":"counterexample|entailed|unknown","distinguishing_behavior":"...","violated_source_atom_ids":["..."],"coverage_reason":"..."}]}
PUBLIC INPUT:
""" + json.dumps(public, ensure_ascii=False)

    @staticmethod
    def _indexed_results(value: Mapping[str, Any], method: str,
                         cases: list[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
        if value.get("method") != method or not isinstance(value.get("results"), list):
            raise ValueError("Representation audit method or results invalid")
        indexed = {str(row.get("case_id")): row for row in value["results"]}
        expected = {str(case["case_id"]) for case in cases}
        if set(indexed) != expected or len(indexed) != len(value["results"]):
            raise ValueError("Representation audit must cover each case exactly once")
        return indexed

    @staticmethod
    def _m3_verdict(row: Mapping[str, Any]) -> str:
        if row.get("target_kind") == "context":
            return "retain"
        if row.get("target_kind") == "uncertain":
            return "unknown"
        statuses = [item.get("status") for item in row.get("assumptions", [])]
        if any(item not in {"supported", "unsupported", "uncertain"} for item in statuses):
            raise ValueError("Invalid M3 assumption status")
        if "unsupported" in statuses or row.get("coverage_without_extra_assumptions") == "no":
            return "reopen"
        if "uncertain" in statuses or row.get("coverage_without_extra_assumptions") == "unknown":
            return "unknown"
        if row.get("coverage_without_extra_assumptions") == "yes":
            return "retain"
        raise ValueError("Invalid M3 verdict")

    @staticmethod
    def _m2_verdict(row: Mapping[str, Any]) -> str:
        if row.get("target_kind") == "context":
            return "retain"
        status = row.get("coverage_status")
        if status == "counterexample" and str(row.get("distinguishing_behavior", "")).strip():
            return "reopen"
        if status == "entailed" and str(row.get("coverage_reason", "")).strip():
            return "retain"
        if status == "unknown" or row.get("target_kind") == "uncertain":
            return "unknown"
        raise ValueError("Invalid M2 verdict")

    def _sync_contract(self) -> None:
        known = {(guard.obligation_id, guard.predicate_id) for guard in self.contract.guards}
        added = []
        for row in self._audit_rows:
            if row["final_verdict"] not in {"reopen", "unknown"}:
                continue
            obligation_id, predicate_id = row["obligation_id"], row["predicate_id"]
            if (obligation_id, predicate_id) in known:
                continue
            added.append(TerminalGuard(
                obligation_id, predicate_id, row["source_text"], row["source_pointer"],
            ))
            known.add((obligation_id, predicate_id))
        if added:
            self.contract = CompletionContract(
                self.contract.task_id, self.contract.guards + tuple(added),
                self.contract.extraction_status,
            )
            self.kernel.contract = self.contract

    def _reopen(self, case: Mapping[str, Any], verdict: str,
                m3: Mapping[str, Any], m2: Mapping[str, Any] | None) -> dict[str, Any]:
        atom_ids = list(case["source_atom_ids"])
        digest = hashlib.sha256("|".join(atom_ids).encode()).hexdigest()[:10]
        obligation_id, predicate_id = f"audit-{digest}", f"audit-{digest}-evidenced"
        pointer = f"instruction://{atom_ids[0]}-{atom_ids[-1]}"
        if obligation_id not in self.state.obligations:
            self.state.introduce_public_requirement(
                obligation_id=obligation_id, predicate_id=predicate_id,
                description=case["source_text"], requirement_source_pointer=pointer,
                contract_span_ids=atom_ids,
                source_event_id=f"representation-audit-{case['case_id']}",
            )
        return {
            **case, "m3": dict(m3), "m2": dict(m2) if m2 else None,
            "final_verdict": verdict, "obligation_id": obligation_id,
            "predicate_id": predicate_id, "source_pointer": pointer,
        }

    def _audit(self) -> None:
        cases = self._cases()
        if not cases:
            self._audit_complete = True
            return
        m3 = self._indexed_results(
            self._call_audit(self._m3_prompt(cases)), "m3_assumption_audit", cases,
        )
        unresolved = [case for case in cases if self._m3_verdict(m3[case["case_id"]]) == "unknown"]
        m2 = ({})
        if unresolved:
            m2 = self._indexed_results(
                self._call_audit(self._m2_prompt(unresolved)),
                "m2_directed_counterexample", unresolved,
            )
        rows = []
        for case in cases:
            m3_row = m3[case["case_id"]]
            verdict = self._m3_verdict(m3_row)
            m2_row = m2.get(case["case_id"])
            if verdict == "unknown":
                verdict = self._m2_verdict(m2_row)
            if verdict in {"reopen", "unknown"}:
                rows.append(self._reopen(case, verdict, m3_row, m2_row))
            else:
                rows.append({**case, "m3": dict(m3_row), "m2": dict(m2_row) if m2_row else None,
                             "final_verdict": verdict})
        self._audit_rows = rows
        self._sync_contract()
        self._audit_complete = True
        emit("representation_assumption_audit", {
            "case_count": len(rows), "reopened": sum(row["final_verdict"] == "reopen" for row in rows),
            "unknown": sum(row["final_verdict"] == "unknown" for row in rows),
            "audit_calls": self._audit_calls, "rows": rows,
        })

    def prepare(self, proposal: Any) -> CompletionDecision | None:
        if not self._audit_complete:
            try:
                self._audit()
            except Exception as exc:
                emit("representation_assumption_audit_error", {
                    "error_type": type(exc).__name__, "message": str(exc)[:500],
                })
                return CompletionDecision(
                    decision="ABSTAIN", reason_codes=("REPRESENTATION_AUDIT_ERROR",),
                )
        return super().prepare(proposal)

    def snapshot(self) -> dict[str, Any]:
        value = super().snapshot()
        value.update({
            "representation_audit_complete": self._audit_complete,
            "representation_audit_calls": self._audit_calls,
            "representation_audit_rows": list(self._audit_rows),
        })
        return value

    def restore_snapshot(self, value: Mapping[str, Any]) -> None:
        super().restore_snapshot(value)
        self._audit_complete = bool(value.get("representation_audit_complete", False))
        self._audit_calls = int(value.get("representation_audit_calls", 0))
        self._audit_rows = list(value.get("representation_audit_rows", []))
        self._sync_contract()
