# Stateful memory v1 SQLite startup gate audit (2026-10-21)

This is a blocked preflight, not a live run or a Harbor certification. The
inspected source was `82bb2d9b360d4dae3352ec7c765a8d7e7ada50df` on
`crs-v0-20261007`; `public/crs-v0-20261007` resolved to that same commit.
Unrelated `GenericAgent-main/monitor_agent_core/**/__pycache__` files were left
untouched. No one-use authorization or SQLite episode was created.

## Deterministic checks

| Check | Actual result |
| --- | --- |
| Core `python -B -m unittest discover -s method_discovery/pma_stateful_memory_v1_20261021 -t . -p 'test_*.py' -q` | 98 tests, OK, Python exit 0 |
| GA bridge `python -B -m unittest discover -s tests -p test_stateful_memory_ga_bridge.py -q`, from `GenericAgent-main`, with `PYTHONPATH` set to the repository root | 13 tests, OK, Python exit 0 |
| Same GA command without the repository `PYTHONPATH` | 13 tests, 11 errors and 1 failure from `ModuleNotFoundError: method_discovery`; environment invocation error, not counted as a passing run |
| `docker version --format '{{.Server.Version}}'` with context `desktop-linux` | Failed: Docker Desktop Linux Engine named pipe absent. `com.docker.service` was stopped; Docker Desktop executable at the checked standard installation path was absent. No container test was attempted. |

A later attempt to start the existing `com.docker.service` failed with
`CouldNotStartService` (the service could not be opened on this machine). It
remained stopped and the Docker Linux Engine pipe remained absent. No system
installation or privilege change was made.

## Sending gates not met

1. `GenericAgent-main/agent_loop.py` accepts the candidate only with
   `GA_STATEFUL_MEMORY_MODE=fake-only`, loopback HTTP and a synthetic key.
   `GenericAgent-main/stateful_memory_bridge.py::from_environment` also rejects
   every non-fake mode and requires finite fake replies.
2. `single_run.py` exposes only `prepare-stateful-fake` and
   `run-stateful-fake`. That route invokes the direct GA test fixture and
   explicitly reports `harbor_tested=false`. `live_launcher.py` has no
   `pma_stateful_memory_v1` candidate branch; `offline_launcher.py` stages GA
   and the PoS branch but not this core package or its pinned BM25 dependency.
   The current source-bound Harbor path therefore cannot certify this method.
3. `budget.py::native_context_preflight` correctly rejects unknown native
   input/window values, but no actual Task or auxiliary send path calls it.
   The available o200k counts are explicitly proxy counts, not verified native
   model tokens. The final payload, output reservation and 2048-token margin
   have not been checked against a bound model window.
4. The existing formal launcher sets a fixed `agent_seconds` deadline,
   `max_turns` defaulting to 300, and an outer deadline. The GA loop itself
   defaults to 40 turns. No candidate-specific unlimited-total semantics have
   been implemented or tested. Benchmark-native limits have not been
   separately frozen for this new candidate.

These are source and environment findings, not claims about provider
compatibility or the candidate's task performance. In particular the direct
GA fake test is not the required same-entry, same-package Harbor/native-SHARED
fake chain. Completing a live provider branch alone would not satisfy the
remaining gates. The requested real episode and official evaluation were not
started: real model requests 0, real Task episodes 0, official evaluations 0.

The next engineering stage must wire and test the candidate-specific formal
route, package identity, effective no-retry transport, native context guard and
total-budget semantics, then obtain a source-bound Harbor fake certification
in a working Docker environment. None of these gates may be replaced by this
audit note or by the historical direct-GA fixture.

## Subsequent Docker correction (same day)

The earlier Docker finding was incomplete: `AGENTS.md` already identifies the
actual installation at `E:\Docker\Desktop`, not the default C: path checked
above. Following its recovery SOP, `Docker Desktop.exe` was launched once.
`docker info --format '{{.ServerVersion}}'` then returned `29.6.1` under the
`desktop-linux` context. The local SQLite image is present with digest
`sha256:f986820b00c74ce75db7288719d364df313fde7c7917bea6eb6352a08431a89f`.
Thus Docker availability is no longer a blocker. The separate formal-route,
source-bound fake-chain and native context guard gates above remain open; no
real run or official evaluation was started during this correction.
