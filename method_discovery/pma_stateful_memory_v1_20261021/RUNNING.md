# Stateful proactive memory v1 — offline only

Run from the repository root with the existing Python environment containing
`tiktoken` 0.9.0. No credentials, private profile or network connection is
read by these commands:

```powershell
python -B -m unittest discover -s method_discovery/pma_stateful_memory_v1_20261021 -t . -p 'test_*.py' -q
python -B -m method_discovery.pma_stateful_memory_v1_20261021.offline_fixture --compact
```

`OFFLINE_CONFIG_EXAMPLE.json` is deliberately `execution_authorized=false`.
`CycleEngine` requires an injected provider callable; it has no default network
transport. The fixture supplies finite fake JSON answers and a local FakeTask.
The method-local database uses standard-library `sqlite3` in temporary
directories; it is not the `sqlite-with-gcov` task environment.

The current implementation has **no live single_run/Harbor adapter** and no
source-bound Docker certification. Do not reinterpret this file as a live run
command or authorization. Future work must implement and audit the host adapter,
full workset-scoped audit contract, actual native context guard and complete
remote checklist before requesting separate real-model authorization.
