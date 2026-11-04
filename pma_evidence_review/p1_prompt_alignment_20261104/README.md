# P1 prompt and tool-description candidate

Base commit: `8b7a87021c5cf033daa2cd92b4ff20e1b8b3feed`.

This branch changes only the P1 requirement agent's system prompt and six tool descriptions, plus the affected P1/P2 compatibility tests. It does not intentionally change tool names, parameters, execution behavior, source retrieval, P2, or task-agent logic.

Status: candidate for review; no offline tests, real-model calls, Task runs, or native evaluations were run for this branch. The local execution environment ran out of temporary space; tests remain pending. Static comparison alone does not establish Python/runtime correctness or semantic improvement.

The manifest, source-identity records, and test counts inherited from the base commit describe that earlier commit only. They do not certify this branch. Regenerate the source identity and delivery manifest from the final candidate and run the affected strict offline tests before any real-model or Task run.
