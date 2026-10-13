# Complete-upstream PMA to GA: offline preparation audit (2026-10-13)

Status: **OFFLINE_BLOCKED; no live run authorized or started.** This is a partial engineering delivery, not a claim of full PMA/GA integration or method effect.

## Baseline and changes

- Initial HEAD/branch: `e65b5fb7f8f2ecc93963acc128a8d58c47949551`, `crs-v0-20261007`. Only pre-existing untracked `GenericAgent-main/monitor_agent_core/**/__pycache__` appeared; it was neither staged nor cleaned.
- Ordered implementation commits before this report: `3d2e2c7d7d3e761591c426956d733b415fdc129e` (verbatim fixed source and public task assets), `466837870077d0f61212ab8ec529af596376addd` (episode and spool), `c1bfd339b27b148c83dc65b65d570070157feabf` (host worker and upstream reference fixture), `1e8fa6682a5502912fb144d89e6f347ce1e25540` (default-off GA event bridge), `d0feca54116dea752e5cf9eaad52bf632550291e` (pinned Harbor forwarding overlay). The GA bridge commit makes a necessary default-off change in `GenericAgent-main/agent_loop.py` and `agentmain.py`; production modification count is therefore not zero. No benchmark Task, verifier, prompt or historical archive was edited.
- `vendor/pma_89e5c0d` contains all 213 tracked files from the fixed upstream tree `65e60a2c82eafffa04dad535e11d0972cda936df`; per-file SHA-256 comparison with the source checkout yielded `mismatches=0`. `LICENSE`, `configs`, `src/memory_agent`, `external/harbor` and templates load from that tree, rather than the old partial `pma_baseline` package.
- Upstream PMA/Harbor versions in a separate Python 3.12.9 environment: `memory-agent==0.1.0`, `harbor==0.1.42`, both editable from the fixed tree. Selected resolved transitive versions are in `RESOLVED_DEPENDENCIES.txt`; the author's historical dependency lock is unknown. No optional Harbor execution backend was installed.

## Call chain that is implemented and tested

`construct_upstream` invokes the unmodified `MemoryEnabledTerminus2` constructor with a complete `BaseLLM` subclass that throws on actor calls. The original memory `LiteLLM`, `MemoryAgent.process`, bank, trigger and user-turn renderer remain active. `PMAEpisode` translates four public GA event shapes into the original reset/accumulation/trigger/pending/save calls. The short `EventClient`/`EventDispatcher` file protocol preserves run/task/event identity, a serial sequence and an accepted request; it never retries an unknown accepted event. The host-private bank/log root is outside the shared request/response spool. `worker_main` supplies one ongoing asyncio loop.

The default-off `GA_PMA_UPSTREAM_ENABLED` branch in the real GA `agent_runner_loop` now sends public `task_start`, `before_actor_call` and `actor_step` events. It retains the original GA Task system/tools/provider loop and injects returned reminders into the current user-turn envelope; the outer `agentmain` finally sends `task_end` on normal or exceptional exit. `harbor_adapter.py` pins the existing Harbor adapter SHA-256 `8a4513c6b28befe747d581d22e94cd2715f20234c63115e0ea424a56d033c3a0` and adds only four forwarded environment names when explicitly selected. This is **not yet an installed end-to-end Harbor launcher or mount certification**.

The independent reference test calls the unmodified upstream `_run_agent_loop` with scripted actor/session I/O and an original memory object. It verifies the first ordinary multi-tool step and following parse-error step against the event adapter. The test does not cover the full requested matrix (completion, budget last turn, both phase failures, etc.). Fake memory responses run through the actual original two-phase `MemoryAgent.process` and parser; only external `LiteLLM.call` is replaced. The production DisabledActorLLM call count is zero.

## Exact offline checks and raw result

1. `git -C <fixed PMA checkout> rev-parse HEAD` → `89e5c0d6aadfe531a1aee42fd290d48be89973dd`; official task checkout → `2fd12b88aafdd04a52c298e3940bcb189f9766d6`.
2. Tracked source SHA-256 loop: `tracked_files=213 mismatches=0`.
3. Python: `C:\Users\hsy\AppData\Local\Temp\pma-ga-py312\Scripts\python.exe -m unittest -v test_episode` in this directory → exit 0, five tests `ok`; the new fifth test passes an actual GA client event through the host dispatcher. An earlier run had an incidental LiteLLM *model cost-map metadata* fetch attempt that timed out; it was not a model/provider inference. Tests now set `LITELLM_LOCAL_MODEL_COST_MAP=True` before importing LiteLLM. The final run had no provider request or metadata warning. This is not a general network-isolation certification.
4. `py -3.13 -m pytest -q tests/test_pma_upstream_ga_bridge.py tests/test_research_agent_loop.py` in `GenericAgent-main` → exit 0, `20 passed in 2.50s`; new branch and default-off route are covered with fake client responses. Import of the pinned Harbor overlay in the existing Harbor Python environment → exit 0, `generic-agent-harbor-pma-upstream` and `True` for all four new forwarded names. This proves import/tuple wiring, not a Harbor trial.
5. `python -m py_compile episode.py event_spool.py worker_main.py test_episode.py` and `import worker_main` → exit 0, `worker_import_ok`. The GA files also passed `py -3.13 -m py_compile`.
6. Original `visualize_memory` and `visualize_memory_trajectory` were called on fake-generated bank/trajectory inside the passing test; both returned HTML paths. This does not certify a real-run rendering pipeline.
7. `docker info --format '{{.ServerVersion}}'` → `29.6.1` after starting the local Desktop Engine. `docker image inspect` for both official task tags → no such image; `ubuntu:24.04` and `python:3.11-slim` are also absent. `docker manifest inspect` for both official tags failed because Docker registry v2 could not be reached. Exact fixed-Dockerfile `docker build --network none --pull=false` attempts for each task exited 1 before any build step: Docker Hub OAuth token fetch failed on `auth.docker.io`. No image was registered as usable. These failures are asset/network limitations, not candidate performance results.
8. `docker ps --format '{{.ID}} {{.Image}} {{.Names}}'` returned no running container during the audit. No official solution or native verifier was executed.

## Assets and information boundary

`assets/public/{task}` holds exact official instruction, task metadata and Docker build context; it is a host-side preparation store, **not a folder to mount wholesale to GA**. Instruction plus the resulting legitimate `/app` contents are the intended model-visible public input; `task.toml`/Dockerfile remain host controls unless the official runtime itself exposes them. `assets/evaluator/{task}/tests` was copied only to the ignored local evaluator role and was **not committed**; official `solution` was not copied. The vendored PMA examples include historical trajectories and must stay host-side, outside future Task/PMA model-visible task mounts. The current fake file-spool unit test alone does not certify actual Docker mount confidentiality.

## Implementation gaps blocking a four-run launch

- The GA branch and byte-pinned Harbor forwarding overlay have now been implemented and tested in isolation, but a trusted run launcher has not yet selected the new Harbor agent, set exact run-bound environment/deadline values, mounted separate GA request/response paths, or started/stopped the host worker with a real task. No actual Harbor-generated GA request with a returned reminder has been captured. Task-only A no-worker behavior in the actual Harbor route and condition parity are untested.
- Both exact task images are missing; their frozen Dockerfiles could not resolve base images. Thus no official-image Docker zero-model end-to-end, task initial tree identity, or verifier-entry/cleanup barrier was validated.
- Full independent original-loop reference cases, event error paths, cancellation/cleanup, duplicate-after-crash behavior, actual Harbor GA initial envelope, model payload/parameter preservation, and PMA LiteLLM endpoint compatibility remain unverified. The current GA branch maps one complete multi-tool batch to one actor attempt in a fake-client test, but not yet in an official task container.
- The existing GA profile is `native_claude_cc_vibe_opus48` in the prior Fyne/Kitex manifest, but its exact use for these Terminal-Bench tasks, Task turn cap, Harbor whole-trial limit, PMA wait bound, and memory model endpoint response identity have not been frozen. In particular the original Terminus2 actor/parser/50-turn settings were not applied to GA.
- The host worker currently records PMA event status but has not installed a transport-boundary phase-failure audit of LiteLLM retries/usage. It cannot yet distinguish all upstream silent error returns from normal no-reminder outcomes in the deployed path. Cross-process deadline and abnormal task-end cleanup behavior require integration certification.

`FOUR_RUN_MANIFEST_DRAFT.json` is deliberately `execution_authorized=false` and `offline_blocked`. It is not a runnable authorization. Completing the listed bridge/mount/asset work and offline tests is required before proposing a real four-run manifest. Real PMA Opus 4.6 compatibility remains a separate future endpoint check; this stage did not call it.

## Calls and evaluation

- Real GA Task, Supervisor/Monitor, PMA model/provider API, native evaluator, training and scoring model: **0** each.
- Scripted PMA-memory fake response calls in the five upstream-adapter tests: 12; scripted upstream fake actor calls: 2; `DisabledActorLLM.call`: 0 except the explicit refusal test, which raised before any inference. GA fake client calls are counted separately in its pytest output.
- No method-effect, GA task success, scorer result or complete upstream reproduction claim is made. Future scoring must use each official native verifier on its own frozen final artifact; missing scores cannot become zero.

The old Fyne/Kitex experiments and this draft are not controls for one another. This report belongs to engineering preparation only.
