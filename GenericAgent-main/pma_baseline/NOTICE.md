# PMA baseline source attribution

MemoryAgent, UniversalMemory and BM25Index are adapted from
https://github.com/yifannnwu/proactive-memory-agent
revision 89e5c0d6aadfe531a1aee42fd290d48be89973dd,
src/memory_agent/memory, under the accompanying Apache-2.0 LICENSE.

memory_agent.py and bm25_search.py preserve upstream logic and prompts.
universal_memory.py replaces unavailable shortuuid.uuid()[:8] with
uuid.uuid4().hex[:8] (opaque random ID alphabet differs; no algorithmic claim).
This is a documented GA/model/transport adaptation, not original-paper replication.

runtime.py supplies task-local initialization, eight public GA steps, synchronous
two-phase calls and one-shot memory notes. It does not use Clean Monitor's active
inspection, interruptions, persistent dialogue or completion approval.
GA has no separately parsed plan field: its public response is supplied as analysis.
The memory bank is task-local; no old run data is imported.
