# PMA natural-language gap reference adapter

Base repository: HYC-hsy/longcontext-monitor-research.
Base commit: abb286f1426096f4bf6eb8f3e46b5e32ffd40b74.
Development main branch supplied by the parent: crs-v0-20261007.
Author source: pinned vendor/pma_89e5c0d, upstream revision
89e5c0d6aadfe531a1aee42fd290d48be89973dd, Apache-2.0.

This is an additive reference implementation, not a registered GA/Harbor candidate.
It does not modify vendor, episode.py, worker_main.py, live_launcher.py, existing
stateful methods, model configuration, or task control. No real model or task was run.

## Construction and persistence contract

Import GapMemory from gap_store and GapMemoryAgent from gap_memory_agent after
putting this directory and its vendor/pma_89e5c0d/src on PYTHONPATH.
Create the bank with GapMemory(), or GapMemory.from_dict(old_bank.to_dict()).
Pass that same object as memory to GapMemoryAgent(task=original_task, llm=llm,
memory=bank, ...original configuration...).

When embedding this adapter, the owner's _memory and the adapter's memory
must point to that same GapMemory. Replacing only _memory_agent while retaining
a different _memory would lose the gap serialization contract. The V1/D1
replacement in episode.py is a construction reference, not a complete patch.
Bind the actual original task explicitly; do not infer it from marker strings in
observations. Reset/reload the bank at the appropriate task boundary.

GapMemory subclasses the actual upstream UniversalMemory. It preserves ordinary
save/delete/status/search methods and the knowledge+procedural length calculation.
The original save_to_file/load_from_file methods dispatch to the extended
to_dict/from_dict. Only official gaps are serialized. Candidate entries and
operation history remain transient. The commit is an in-memory whole-group
reference swap in the serial PMA cycle; it does not make upstream disk writes
crash-atomic. Disk persistence retains the upstream save contract.
clear(keep_status=False) retains the parent's status/ordinary-memory clearing
semantics and also clears official gaps, the candidate and its changes. No old
task gaps survive a cleared bank into the next cycle.

## Execution and review

The wrapper calls the actual MemoryAgent.process. Upstream retains the phase
order and Phase2 XML response parser. The adapter uses upstream structured/XML
tool parsers and delegates ordinary operations to the upstream executor once.
Only gap save/delete operations are staged. Returned stage_save_gap and
stage_delete_gap records mean staging succeeded, not that review accepted them.
last_gap_report records acceptance/staleness, review inputs/replies, repair count
and the actual Phase2 prompt. It is separate from the formal memory snapshot.

Every successful maintenance cycle reviews the whole candidate, including
unchanged gaps and omissions, even with no proposed diff. The reviewer receives
the original task, exact process observation, old/candidate entries and changes,
plus the original PMA _format_memory_bank(observation) projection. This reuses the
existing BM25 rules, adds no history or retrieval mechanism, and remains a fallible
summary that cannot override the task or actual observations.
The adapter does not retrieve new evidence or receive hidden evaluation results.
It retains only the materials actually passed into this PMA cycle.

Review responses must completely match ACCEPT, ACCEPT: reason, or REVISE: feedback.
Acceptance needs no reason; when a colon is present its reason must be non-empty.
Revision always requires non-empty feedback. Reasons and feedback may span lines.
Empty, malformed, conflicting decisions, refusal prose, or tool-bearing responses
are invalid and retain the old gap group. Valid REVISE gets at most one gap-only
repair and one review. Repair starts from the first candidate; it cannot execute
ordinary operations, even if a model emits them. Review/repair/commit helper
errors retain old gaps and continue original Phase2 with a stale indication.
Repair respects use_structured_tools exactly as Phase1 does: when disabled, no
tools argument is sent and the original text/XML fallback parser handles the reply.
Cancellation, KeyboardInterrupt and SystemExit are not converted to silence.

No deterministic validator claims to assess semantic truth of a well-formed
ACCEPT reason. The model review is fallible. Offline tests cannot establish
review quality, reminder quality, or an improvement on real tasks.

The Phase2 call hook reviews and then rebuilds the prompt from the settled bank.
The wrapper replaces result.user_prompt_phase2 with the actual sent prompt.
This avoids reporting the pre-review prompt built internally by upstream process.

## Prompt differences from U

Phase1 retains PHASE1_SYSTEM and adds the gap instructions: task-specific initial
acceptance expectations; information gaps; unmet goals; unverified acceptance;
testing coverage/assertions/expected results/input contracts/execution validity.
No labels are parsed. Unverified acceptance is not automatically a test defect;
a valid failing test may resolve testing insufficiency and establish a functional gap.

Phase2 retains the original output contract and default no_intervention. Three
exact original rules are replaced, following the limited V1 approach, to allow
repeating visible information when current behavior contradicts or fails to apply
it. The added text emphasizes relevant gaps without making every pending item a
mandatory reminder, and grounds COMPLETE/gap conflicts in task and observations.
This does not adopt the full D1 prompt. A replacement-contract mismatch falls
back to the original Phase2 system with a visible assistance-unavailable note.

BANK_TOOLS and PHASE2_SYSTEM are never mutated. Gap entries are displayed outside
the original memory bank; they do not affect the BM25 threshold or top-k policy.

## Offline verification

Prefer the development machine's existing Python/virtual environment that already
runs PMA. Python 3.12.13 was the actual reference test environment, not a mandatory
version. Revalidate in the existing local environment; make only minimal fixes for
specific compatibility errors, without proactively rebuilding or switching environments.
The narrow memory imports require the real shortuuid package; BM25 and trigger use
the standard library. These tests
use unittest and scripted model responses, not Harbor or a provider. They import
and execute the actual vendor MemoryAgent, UniversalMemory and MemoryEntry.

From repository root, with a prepared environment:

```sh
D=method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$D:$D/vendor/pma_89e5c0d/src" \
  python -m unittest discover -s "$D/tests" -p 'test_gap*.py' -v
```

There are 26 test methods covering the actual process and parsers, prompt-record
identity, whole-group acceptance/rollback, unchanged entries/omissions, ordinary
operation independence, one repair limit, malformed review, helper failures,
cancellation/termination, upstream serialization and unchanged U/BM25 behavior.
The review corrections also cover clear/reset, bare acceptance and multiline
feedback, XML-only repair, and ordinary-memory projection without replayed writes.

Current execution status: 26 tests passed on Python 3.12.13 in 0.076 seconds.
The tests used the real pinned shortuuid source described below, imported only
through the test process's PYTHONPATH. No model or real task was called.
Source AST, patch application and pinned-source hash checks also passed.

Environment observed: system Python 3.9.6; available Homebrew 3.10.20, 3.11.15,
3.12.13; Git 2.50.1. A task-local .venv was created with 3.11, then .venv312 with
3.12 after checking the formal vendor requirement. unittest/asyncio are present;
shortuuid and pytest are absent. pytest is not needed for these tests.

Exact installation attempts, all confined to the task workspace:

```sh
.venv/bin/python -m pip --isolated install --disable-pip-version-check \
  --no-cache-dir --retries 0 --timeout 15 shortuuid
.venv312/bin/python -m pip --isolated install --index-url https://pypi.org/simple \
  --disable-pip-version-check --no-cache-dir --retries 0 --timeout 15 shortuuid==1.0.13
```

Both returned `Could not find a version that satisfies the requirement ...
(from versions: none)` and `No matching distribution found ...`. A diagnostic
repeat of the second command with `-v` added no network details. A read-only
urllib request for https://pypi.org/pypi/shortuuid/1.0.13/json then failed with
`URLError: [Errno 8] nodename nor servname provided, or not known`.
These failed attempts were stopped; they were not approval rejections.

The parent supplied a verified alternative source: skorokithakis/shortuuid tag
v1.0.13, commit 16374d288c796faa2aee5789ed649c3ed7cdd9be. The GitHub connector
read shortuuid/__init__.py, shortuuid/main.py, pyproject.toml and COPYING at that
exact commit into a separate task-local dependency cache, outside this patch.
Each file was checked against its Git blob SHA. The narrow import uses only
the first two Python files and standard-library dependencies; no substitute
module or global installation was used. The source pyproject version is 1.0.13;
its __init__.__version__ still says 1.0.11. This upstream discrepancy was retained
without editing, and identity is established by the fixed commit and blob hashes.

Actual successful command from the preparation workspace:

```sh
task_driver=source/method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="dependency_cache/shortuuid_v1_0_13:$task_driver:$task_driver/vendor/pma_89e5c0d/src" \
  .venv312/bin/python -m unittest discover -s "$task_driver/tests" -p 'test_gap*.py' -v
```

Exit code 0; 26 tests passed. This establishes only the tested offline engineering
contracts, not model review quality or effectiveness on real tasks.

## Scope

This delivery stops at the method implementation and offline tests. It includes
no experiment wiring, runner registration, Harbor certification or real execution.
There is no added HTTP counter, token ceiling, completion gate or frontier graph.
