# Offline candidate commands

From the repository root, Python 3.13 with the existing GA dependencies:

```powershell
C:\Python313\python.exe -B -m unittest -v method_discovery.pos_upstream_ga_v1_20261017.test_citation_fix method_discovery.pos_pma_complement_v1_20261019.test_memory_adapter method_discovery.pos_pma_complement_v1_20261019.test_candidate_core method_discovery.pos_pma_complement_v1_20261019.test_worker_fake method_discovery.pos_pma_complement_v1_20261019.test_candidate_ga_seam
C:\Python313\python.exe -B method_discovery/pos_upstream_ga_v1_20261017/test_ga_seam.py -q
```

The generic preparer selects `--condition P --research-candidate
pos_pma_complement_v1` with a fresh output directory and the existing fixed
official-source checkout, private Task profile and image. `prepare` sets
`execution_authorized=false`; it is not permission to run a formal Task.
The analogous `PoS` and `PoS-citation-fixed` identities remain independent.

The zero-model Docker fixture uses the existing `single_run_fixture` command,
the registered `pos-synthetic-file-http` synthetic package and
`--research-candidate pos_pma_complement_v1`. Its fake transport has no
provider fallback; its Task service and sentinel are synthetic. It requires
the fixed Harbor source, current Docker daemon and the pre-existing runtime.
The output directory must not exist. Exact command and result belong in the
audit TXT, not in a live authorization.

Future profile execution would require an independently reviewed candidate
PMA role transport, fresh source-bound certification, a frozen private profile
and the existing one-use authorization. This branch currently rejects
candidate profile mode before any HTTP send. No live command is executable
from this document.
