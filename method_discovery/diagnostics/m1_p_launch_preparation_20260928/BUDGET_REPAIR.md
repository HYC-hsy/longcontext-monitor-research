# Finite budget-boundary repair (no scientific execution)

Only common experimental resource accounting changes. M1 source, P body,
task originals and scientific pilot specification remain unchanged.

- Admission reserves `attempt_limit * per_attempt_reserve` for input and output
  across record/panel pending calls. Count stays one logical call; each admitted
  send counts separately. This conservatively denies the audited 80/100 case
  before even the first attempt when three attempts are permitted.
- Reservation is an estimate, not a certified bound. Actual per-attempt usage
  exceeding it immediately pauses panel admissions and subsequent attempts,
  including other pending records. Finish accounts received usage, preserves
  raw usage/failure records and returns blocked. Already sent work is not revoked.
- Sent attempt without complete usage pauses the panel before another retry
  or at finish. Its envelope remains in `unresolved`; known buckets still enter
  totals. Unsatisfied portions are not released as zero. No automatic resume.
- Task stream content may reach its caller before final settlement stops it.
  A fake streaming base through the actual experimental wrapper demonstrates
  content delivery followed by BudgetStop. No full Task action suppression is
  claimed. Monitor completed-response return is guarded by its wrapper finish.

Tests retain the original five checks, with the old retry fixture updated to
provide usage for two known attempts and omit the third. New cases cover all
four reservation caps, known retries, cross-record unknown usage, partial usage,
estimate breach including other pending sends, and streaming stop order.
Full-suite captures also recheck M1/P request parity without budget pressure.

The initial repair run's actual failure (obsolete fixture assumed unknown
attempts could retry) is retained as `offline_receipts/budget_repair_first_run.*`.
Latest command and raw final stdout/stderr are in the usual `offline_receipts`.
Synthetic usage is engineering data, not paid model cost or method evidence.

Final command: `python method_discovery/diagnostics/m1_p_launch_preparation_20260928/run_checks.py --supervisor-source <exact-M1-worktree>`.
Actual final result: **15 passed in 20.38s**, exit 0. Original five retained;
four parameterized cap cases and six additional boundary cases bring total to
15. Known pytest atexit cleanup warning references the pre-existing Windows
`pytest-951` permission failure; raw stderr retained, no test failure.
Eight final fake transport captures (six Supervisor, two Task parser captures)
and zero external/model requests; request parity remains unchanged. No full
online Task or container execution occurred.

Panel pause denies later admission/attempt checks. It cannot cancel an HTTP
operation that has already passed its admission check or retract streamed
content; admission-to-send races and in-flight excess are not a hard cap claim.

Money cap unimplemented/unapproved. Linux container, image digest, mounts,
full Task/Monitor processes and watchdog remain NOT COVERED. No Docker retry,
model service, benchmark, verifier or pilot execution is authorized here.
