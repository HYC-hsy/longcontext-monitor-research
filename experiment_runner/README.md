# Dataset runner

Configure the pinned dataset, local runtime/profile paths, default method, and
limits once in a local JSON file. The file contains **paths**, not credentials.
[`examples/sqlite.ga-only.json`](examples/sqlite.ga-only.json) shows the shape.
Keep your filled-in file private.

From the repository root, using the already installed runtime Python:

```sh
# One task
python -m experiment_runner run --config experiment.local.json --method ga-only --task sqlite-with-gcov --output runs/ga-sqlite-01

# Several tasks, in the order written
python -m experiment_runner run --config experiment.local.json --method pma-gap-evidence --task sqlite-with-gcov --task fix-ocaml-gc --output runs/pma-two-01

# Every compatible task in the pinned dataset
python -m experiment_runner run --config experiment.local.json --method ga-only --all-tasks --output runs/ga-all-01
```

`run` creates a new result directory, prepares each slot, binds its method and
source identity, and starts the existing GA/Harbor driver. There is no separate
user-facing certificate or authorization-file step. Internal one-use binding
still prevents an already allocated slot from being silently run twice. Choose
a **new** output directory for every new experiment. `plan` and `prepare` remain
optional read-only/zero-model inspection commands; their output is not needed
for an ordinary `run`.

`--method` overrides the config method for every selected slot. Repeated
`--task` or `--all-tasks` replaces the config's `slots`; with no overrides, the
config's slots and method are used unchanged. `--all-tasks` means the entire
pinned task pool, **not** a previously published 20-task subset. Put a frozen
subset and desired repeat/occurrence values in `slots` when needed. The current
driver runs slots serially and refuses `execution: parallel` rather than
silently changing the schedule.

The same `runtime_policy` object applies to all selected slots:

```json
{
  "agent_timeout": "uncapped",
  "task_turns": "uncapped",
  "verifier_timeout": "official"
}
```

`agent_timeout` accepts `official`, a positive number of seconds, or
`uncapped`; `task_turns` accepts `method_default`, a positive integer, or
`uncapped`. The verifier remains on its official limit. An uncapped Agent run
is a diagnostic run, not an official-time-limit result. The selected plan
prints planned limits; the run archive records the limits actually applied.

Method names include `ga-only` (pure GA condition A/U), `pma`, `pma-v1`,
`pma-d1`, `pma-stateful`, `pma-gap`, `pma-gap-evidence`, and the registered PoS
variants. A new mechanism must have a real adapter; inventing a name does not
make it runnable. Method-specific options such as `citation_review_gate` and
`citation_review_strategy` belong in the same config and remain opt-in. Do not
put them in a pure-GA config. The GA adapter's native prompts, tool loop,
history, and task completion behavior are not replaced by the runner.

`catalog --config ... --output catalog.json` lists public task identities at
the pinned dataset commit; `plan --config ... --output plan.json` resolves a
proposed run without starting it. Relative paths in the config are resolved
relative to the config file. Local profiles and output archives may contain
private data; inspect before publishing. No model call is made by `catalog`,
`plan`, or `prepare`.

The catalog can read compatible task packages from a pinned local Git commit.
The current execution adapter is still bound to its pinned Terminal-Bench task
pool and Harbor source. A different dataset format needs another adapter, not
a change to GA or to every monitor method. Reward zero is a result, not a
reason to retry; an interrupted or uncertain run retains its claim and logs.
