# First-decision protocol check

Execution code: `a0c588722fbcde679d205abd930287ff66ef217b`. This is a mechanical check of the four completed follow-on runs, not a judgment of reminder usefulness.

The `host_private/archive/memory_cycle.jsonl` records in the ZIP contain 119 wakes and 594 visible manager responses. Exactly one valid decision was accepted in each wake. The first accepted decisions were 114 `no_intervention` and five `context_for_action`. Later decision tags appeared 178 times, and 37 wakes contained a later tag contrary to the first accepted decision. Those later tags did not replace the recorded first decision.

| Task | Wakes | First `context_for_action` | First `no_intervention` | Wakes with conflicting later tag | Reminder in actual subsequent Task request attempt |
| --- | ---: | ---: | ---: | ---: | ---: |
| make-mips-interpreter | 97 | 0 | 97 | 24 | 0 |
| merge-diff-arc-agi-task | 6 | 2 | 4 | 4 | 2 |
| reshard-c4-data | 5 | 1 | 4 | 4 | 1 |
| largest-eigenval | 11 | 2 | 9 | 5 | 2 |

For example, merge-diff cycle steps 4 and 12 first accepted `context_for_action` and later emitted `no_intervention`; reminders appear in `before_actor_call` attempts 5 and 13 and have matching `provider_request_attempt` records. Cycle steps 16 and 20 first accepted `no_intervention` and later emitted `context_for_action`; those later tags did not create reminders. Reshard cycle step 12 and largest-eigenval steps 12 and 16 show the same first-reminder/later-no-intervention pattern. MIPS had 24 opposite later-tag wakes but no accepted reminder and no sent reminder.

The ZIP includes the cycle records, `events.jsonl`, Task `research_events.jsonl`, and the derived `*.reminders.json` file for cross-checking. The last column requires a matching next Task request attempt, not merely a generated or queued reminder. It does **not** prove the Task Agent adopted the content or that the reminder was helpful. The first completed rstan task is archived separately at commit `880a9be43c59b400181d9a8ed918372930cef63f`.
