# Dynamic Observer v0c adoption pilot — mechanical run facts

This is an event locator, not a mechanism-adoption or efficacy judgment. The two runs were registered before their first model requests in `method_discovery/diagnostics/dynamic_observer_v0c_adoption_20261001/PREREGISTRATION.json`. No record-level rerun or online treatment change occurred. The archived ADER-v2c runs are historical background, not causal controls.

## Identity and termination

| Record | Run ID | Task | Online end | Infrastructure check |
| --- | --- | --- | --- | --- |
| r1 | `dynamic-observer-v0c-adoption-20261001-01` | `roadmapbench:fyn-2.2.0-roadmap` | `agent_phase_completed` | runner `valid=true`, no validation errors |
| r2 | `dynamic-observer-v0c-adoption-20261001-02` | `roadmapbench:ktx-0.13.0-roadmap` | `agent_phase_completed` | runner `valid=true`, no validation errors |

Both materialized `e52107808527cb42ad2169db721b69b450a674fc` (tree `c54121ef93c45e811d4dbd9f8cb5dbdb80fa7fb8`; source Git archive SHA-256 `962a8f689ae8d623c979aeca402079b08239b47c676067f342271c4daa4fdcd5`). Task and Supervisor private-profile SHA-256 values were respectively `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e` and `cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1`; both use `claude-opus-4-8`. Fyne task-tree SHA-256 is `928e4d98926e9c6038f2538ec960be19fa1fb199bfc11f06e3fe01a7d50259d6`, image `sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`. Kitex task-tree SHA-256 is `19986c7804fe51795c8923c478a63e9d3595a2394f10229aa1905b468af8e0ab`, image `sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e`. The actual first `review_context` in each `dialogue.jsonl` contains the v0c decision-critical measurement contract and the same seven Monitor tools. Per-run source/config/proof identities are in `r1/` and `r2/`.

The existing Roadmap runner mechanically executed its native verifier after the Task Agent phase; `online_checker_feedback=false` in both proof manifests. Terminal evaluation is listed separately below. It was not fed back into either online run.

## Counts and raw locator format

The exact request, attempt, token-bucket, tool and working-mutation counts are in `RUN_FACTS.json`. `MECHANICAL_EVENT_INDEX.json` lists every review, tool call, tool error, working mutation, root checkpoint, runtime update and control receipt with raw line numbers. `ADOPTION_LOCATOR_INDEX.json` links all observation calls to preceding visible model output and tool-result lines, lists public Task code/mutation calls, and includes literal wording-search hits **without treating them as adoption verdicts**. A `dialogue_line` refers to `rN/agent/monitor/monitor_private/audit/dialogue.jsonl`; `progress_line` refers to the adjacent `progress.jsonl`; `public_event_line` refers to `rN/agent/monitor/task_evidence/public_events.jsonl`.

| Mechanical count | Fyne r1 | Kitex r2 |
| --- | ---: | ---: |
| Task requests ready / provider attempts | 113 / 113 | 182 / 183 |
| Supervisor logical requests / attempts | 79 / 79 | 100 / 100 |
| Reviews; follow / patrol waits | 14; 8 / 5 | 23; 11 / 11 |
| Tool calls: read / code / write / patch | 48 / 2 / 11 / 1 | 46 / 14 / 6 / 16 |
| Interventions / completion proposals / allow calls | 4 / 2 / 1 | 4 / 1 / 1 |
| Working mutations / maximum chars | 12 / 1144 | 22 / 2223 |
| Online Task event span (seconds) | 1803.665 | 2207.713 |

Task and Supervisor input, output, cache-creation and cache-read token sums are separately preserved in `RUN_FACTS.json`, not conflated. All Supervisor request-attempt outcomes were `success` (79 and 100); Kitex had one more Task provider attempt than ready request. Four r1 and four r2 Monitor tool-result records have `status=error`, whose exact tool IDs and raw results remain in `MECHANICAL_EVENT_INDEX.json` and dialogue. No explicit `cancelled`/`interrupted` Monitor tool-result status was counted; this is not a claim that no Task-side interruption occurred.

## Mechanism-event navigation, not classification

- Pre-result measurement relation and possible proxy/substitution wording: `ADOPTION_LOCATOR_INDEX.json` gives the full set of 50 Fyne and 60 Kitex `file_read`/`code_run` observation calls, each linked to its preceding visible model-output line and resulting tool-result line. Its wording groups are search candidates only. Ordinary navigation is not scored as needing A/B commitment. No adoption conclusion is drawn from a missing or present keyword.
- Old-ground transport windows: Fyne working revisions appear at dialogue lines 17, 71, 98, 135, 157, 201, 253, 282, 304, 319, 376 and 418; Kitex at 50, 72, 94, 121, 165, 199, 228, 255, 282, 316, 333, 350, 367, 384, 401, 418, 435, 452, 469, 491, 508 and 525. Intervening Task `file_write`/`file_patch`/`code_run` calls are individually indexed by public-event line, archive sequence and task turn in `ADOPTION_LOCATOR_INDEX.json`. Whether any old ground was semantically Carried, Withheld/Requalified, Reopened, Pruned or reused without qualification requires reading these raw chains; literal terminology alone did not establish those categories.
- Root/snapshot locations: Fyne root checkpoints are `progress.jsonl` lines 649 (`completion-1`) and 765 (`completion-2`); the adjacent final reviews span dialogue lines 336–389 and 390–425. Kitex has checkpoint `progress.jsonl` line 980 (`completion-1`) and final review dialogue lines 534–564. The corresponding public completion proposals, working revisions, observations and control results are linked in both JSON indices.
- Intervention/recovery locations: Fyne `intervene` tool calls occur at dialogue lines 81, 226, 324 and 381; Kitex at 194, 250, 311 and 486. `delivery_feedback.jsonl` and subsequent reviews provide delivery and follow-up evidence. These locations do not by themselves establish recovery success or eventual relaxation.
- Representation/protocol burden: mutation lengths in order are in `RUN_FACTS.json`. The literal fixed observer headings `Contrast:`, `Measurement:`, `Basis:`, `Reach:`, `Anchor:` and `Transport:` were not found as headings in working-file tool arguments. The first working writes nevertheless contain ordinary task/decision headings (Fyne dialogue line 17; Kitex line 50); the raw note text is preserved. Keyword matches or repeated contract language are not scored as protocol creep without raw review.

The archived raw files include original public task, Task public events/synopsis, Task telemetry/output, full Supervisor dialogue/progress/provider history/attempts/usage, working state and mutation receipts, commands/results, delivery feedback, runtime receipts, root-checkpoint metadata, effective config and proof identity, OTel trace summary, and terminal verifier artifacts. `r1/RAW_FILE_MANIFEST.json` and `r2/RAW_FILE_MANIFEST.json` record per-file bytes and SHA-256. The larger live checkpoint workspace directories remain in the local output tree and were not silently substituted with a reconstructed state.

## Terminal evaluation — separate from mechanism facts

The fixed runner's post-termination native verifier reported Fyne **2/7**, reward **0.1818181818**, and Kitex **4/6**, reward **0.6**. Raw verifier outputs are under each `rN/verifier/`. Neither score is used here to explain observer adoption or control behavior.
