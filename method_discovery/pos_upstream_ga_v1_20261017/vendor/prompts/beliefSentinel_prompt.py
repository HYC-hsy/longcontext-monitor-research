"""Consistency auditing, issue repair, and execution-progress prompts."""

from __future__ import annotations

import json


CONSISTENCY_SYSTEM_PROMPT = """Validate one candidate Belief transition.
Report an issue only when a changed State, Relation, or Gap is internally
inconsistent or contradicts the supplied raw trajectory. Absence from a partial
observation is not contradiction. Return at most one evidence-grounded issue and
do not propose environment actions."""

SHARED_AUDIT_SEMANTICS_V1 = """Audit the transition from belief_before (a revisable prior
interpretation) to candidate_belief (the proposed state AFTER this action). The action
describes what was attempted, not proof of success; observation is the returned evidence.
Inspect each added, changed, or deleted State, Relation and Gap, including frontier
changes, against the actual observation and original task requirements. A new fact need
not have existed before: allow a result supported by this step. New evidence can replace
an old inference. Do not conflate copying with moving or deleting: a destination copy
alone does not prove the source vanished. Silence in an observation is not proof of
absence. Additions, deletions and gap closure still require support; local success does
not establish a broader requirement or weaken the task. For each issue name the specific
candidate change and why its evidence is insufficient; difference from the prior state
alone is not an issue. For example, a tool reporting that a new file was created can
support adding that file, while merely requesting its creation cannot support deleting
an existing source file. The candidate_changes map locates differences; it is not
independent evidence. Return at most one grounded issue."""


PROGRESS_SYSTEM_PROMPT = """Label whether the finalized execution transition made
task-relevant progress on the Active Gap. progress=1 only when it reduced the
Gap, acquired evidence needed for it, or established a State/Relation on a
plausible path to the Goal. A repeated failure or irrelevant change is 0.
Return only the requested JSON object."""


EXECUTION_PROGRESS_EXAMPLE = """Example: obtaining new evidence that narrows the
Active Gap is progress; repeating the same failed or unchanged result is not
progress."""


def build_local_audit_prompt(audit_input: dict) -> list[dict[str, str]]:
    """Build local audit prompt."""

    return [
        {"role": "system", "content": CONSISTENCY_SYSTEM_PROMPT +
         ("\n\n" + SHARED_AUDIT_SEMANTICS_V1 if audit_input.get(
             'audit_semantics_version') == 'pos-shared-audit-semantics-v1' else '')},
        {
            "role": "user",
            "content": (
                json.dumps(audit_input, ensure_ascii=False)
                + '\nReturn JSON: {"issues": [{"targets": ["id or gap target"], '
                '"issue_type": "internal or external", '
                '"problem": "...", "evidence_step": 0, '
                '"evidence_quote": "verbatim evidence", '
                '"evidence": "...", "suggestion": "belief correction"}]}. '
                "Use an empty issues list when the candidate is consistent."
            ),
        },
    ]


def build_global_audit_prompt(audit_input: dict) -> list[dict[str, str]]:
    """Build global audit prompt."""

    return build_local_audit_prompt(audit_input)


def build_execution_progress_prompt(
    progress_input: dict,
) -> list[dict[str, str]]:
    """Build execution progress prompt."""

    return [
        {"role": "system", "content": PROGRESS_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                json.dumps(progress_input, ensure_ascii=False)
                + "\n"
                + EXECUTION_PROGRESS_EXAMPLE
                + '\nReturn JSON: {"progress": 0, "score": 0.0, '
                '"affected_record_ids": [], "reason": "..."}.'
            ),
        },
    ]


def build_sentinel_repair_prompt(
    messages: list[dict[str, str]],
    raw_response: str,
) -> list[dict[str, str]]:
    """Build sentinel repair prompt."""

    return messages + [
        {
            "role": "user",
            "content": "Return the same validation result as one valid JSON object.",
        }
    ]


def build_progress_repair_prompt(
    messages: list[dict[str, str]],
    raw_response: str,
) -> list[dict[str, str]]:
    """Build progress repair prompt."""

    return messages + [
        {
            "role": "user",
            "content": "Return the same progress judgment as one valid JSON object.",
        }
    ]
