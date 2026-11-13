# Preserve code in reminder transmission

Base: `7fbbf9d653d65e353e5a5d3ca29763f390911540`.

## Scope

Fix only the final-decision parser's lossy extraction. The previous parser deleted fenced code before extracting `<context_for_action>`; real ARC call 21 lost its filter snippet and real RStan call 31 lost posterior-mean/output snippets. These original replies came from public archive `565cbd6f48124c61fc05906a83367b7bec30936c`.

Protocol tags are now recognized on a same-length masked view of code fences. The accepted reminder is sliced from the original public content, not the mask. Code fences and their contents are preserved. Decision-like or legacy hidden-like tags inside literal code are not interpreted as control. Legacy hidden spans outside literal code remain excluded; malformed/nested hidden spans, conflicting decisions, and unclosed/nonterminal decisions still fail closed. Existing surrounding-whitespace normalization and one-time host injection are unchanged.

No prompt, model, tools, wake interval, history policy, or experiment method was changed. No real Task, model call, native evaluation, or paid run was started.

## Verification

- Replayed all 13 archived reminders: old parser reproduces 11/13 exact bodies, fixed parser 13/13. ARC retained 748 vs old 709 characters; RStan retained 1,488 vs old 880. Results: `tests/fixtures/reminder_code_replay_results.json`.
- Both actual affected public replies are pinned as regression fixtures. Their semantic claims are **not endorsed**; tests verify faithful transport, not correctness of advice.
- Tests exercise the actual manager process and host injection wrapper, verify exact body equality and one-time consumption, and cover backtick/tilde fences, code-only reminders, literal control/hidden tags, external fenced examples, and invalid decisions.
- Focused parser/prompt/wiring checks: 57 passed.
- Predictive/prompt plus new transport regressions: 186 passed and 4 subtests passed (Linux/Python 3.12, three existing Pydantic warnings).
- Broader selection including continuous-integrity checks: 224 passed, 5 failed and 4 subtests passed. Replacing the production module with the exact parent and rerunning the entire continuous-integrity file reproduced the same 5 failures (38 passed): four compression-telemetry cases with read-context enabled and one source-file set assertion. They were not changed or silently waived in this repair.
- Existing AST guard was explicitly repinned for this authorized runtime change; exact approved prompt equality and negative runtime-mutation detection remain tested.
- Windows and full-repository suite were not run; no claim that every repository test is green or that task success improves.
