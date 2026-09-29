# Empty preflight directory repair

User authorized repair and resumption after the zero-model startup failure.
Only the experimental launcher creates the empty `task-source/GenericAgent-main/temp`
directory before invoking the original runner. Git-exported Task/M1 source bytes,
P, parameters and the original runner are unchanged. The final isolated bundle
continues to exclude `temp/`; its task setup creates a separate writable runtime.

The original `resolve_model(0)` and `resolve_agent_hosts(0)` were executed on the
failed preparation with only the missing empty directory supplied. Both passed
in Docker Linux; no model request or Task run occurred. Raw identity result:
`original_resolver_check.json`. The directory remained empty afterward.

Thin-entry fake-boundary check passed with new assertions for an empty preflight
directory and its absence from the final bundle. `test_linux_preparation.py`:
3 passed, exit 0, two existing pytest cache permission warnings plus the known
Windows atexit cleanup warning; neither changed the exit status. Original failure
and authorization are retained unchanged.

Failed zero-model preparation is retained locally under `execution_stop_20260929/`
before the same record/run identity is resumed. It is not a second scientific
record. Secret-bearing exports remain unpublished. The repaired launcher receives
a new authorization hash; the prior authorization remains archived.
