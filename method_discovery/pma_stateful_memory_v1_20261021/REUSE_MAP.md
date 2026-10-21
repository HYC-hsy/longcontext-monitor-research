# D/A/N reuse map

| Category | Fixed source / local function | Actual use and boundary |
| --- | --- | --- |
| Direct (D) | PMA `89e5c0d6aadfe531a1aee42fd290d48be89973dd` `src/memory_agent/memory/bm25_search.py` | `retrieval._pinned_bm25` loads and verifies the fixed LF-normalized source hash `9d4169c482e3aeef11ace9d6d87dbadc015b0a1ac2d4c1906b4b0f901bbe376b`; the original ranking code runs. The vendor file and its LICENSE are unchanged. |
| Adaptation (A) | Host EventSeq/source ledger, SQLite transaction backend, finite provider callback | `store.MemoryStore`, `source.SourceCatalog`, `engine.CycleEngine`, `reminder.attach_once`. These are new method-local adapters, not author PMA functions. No GA live transport is wired. |
| New candidate (N) | Unified single B=(G,W,DeltaE,DeltaA,F), joint proposal/audit/one-credit repair/postcommit selection | `schema`, `proposal`, `audit`, `engine`, `prompts`, `reminder`. These implement a candidate protocol; they are not a reproduction of original PMA or PoS. |
| Not directly reused | PoS fixed `6818cfa6434dbc91fcf67f0b3eb12a91db47433f` | State/audit concepts inform the fixed unified specification; this package does not execute PoS manager/Sentinel. It would be inaccurate to label it direct code reuse. |

The existing GA-only, PMA, PoS and shared-view source paths are untouched by
this stage. The new package is opt-in through a finite offline entry and does
not silently alter their defaults.
