# Path-first control v0: four-trial development campaign

This is a development exploration, not a randomized causal comparison. The
production candidate is `7911aefd770788d78041e324c4033a16e607fba4`,
branched from `914db59abdf7f4341d0c16503efbbea5fe5b5085`.

The fixed order is Fyne BASE, Fyne PATH, Kitex PATH, Kitex BASE, using the
opaque IDs and identities in `PLAN.json`. Each is a fresh complete trial. Both
conditions retain DCEC, WTV, the original seven Monitor tools, the same
Opus 4.8 Task/Monitor model settings, review and task limits, root lifecycle,
gateway route, isolation, and native post-termination evaluation. R5 view and
intent are off. The only planned model-visible delta is the opt-in replacement
of three DCEC cognitive texts and the ordinary-request public-event window.

The PATH window reads complete records of `task/public_events.jsonl`. It shows
the pending root-handoff event when present, otherwise the latest complete
event, plus the latest distinct complete event with a nonempty tool return.
Each event's calls and returns remain together. Source fields are limited to
`text`, `tool_calls`, `tool_results`, `task_turn`, `boundary`,
`archive_sequence` and line locator. The fixed 2400-character cap includes
guidance and visible-boundary notices. With two events, the remaining budget
is divided in half for the first; calls and returns receive 36% and 42% of
that event's allowance, then text receives the remainder. With one event it
gets the remaining budget. Omission is marked with a source reread location.
An incomplete trailing line is not treated as a complete event.

The research entry reuses the installed runner and UC-R5 capture/send-gate
bridge, with a campaign-specific identity adapter. It does not bypass the
original task input, image, mount, network, terminal workspace-capture or
verifier-release checks. Credentials remain in private profile/bundle files.

Normal low score, model tool errors, inadequate adoption, and budget endings
are results and do not cause a rerun. Confirmed identity, isolation, candidate
wiring or infrastructure failure stops later slots. No extra conditions or
prior UC-R5 slots are authorized here.
