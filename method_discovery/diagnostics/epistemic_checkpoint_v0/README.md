# Epistemic Checkpoint Minimal Instrumentation v0

Research-only, one-shot `capture_checkpoint(...)` and `verify_checkpoint(...)`.
Neither function is wired into the Monitor runtime, a model request, a tool, or
the Task Agent. A caller selects the boundary and owns the short Task-write
barrier; the capture API never decides whether a ground is consequential.

`capture_checkpoint` requires a callback that attests `task_writes_paused=true`,
`supervisor_idle=true`, and zero in-flight requests/tools while returning the
same review, request, cursor, turn, and control state before and after copying.
It compares source workspace content before and after the copy with the copied
content. A changing boundary or file fails closed: `capture_status.json` says
`incomplete`, and no `complete.json` seal is left. The caller must not treat a
false barrier attestation as a real pause. A mutation that occurs and reverses
between scans is not detectable without a genuine host write barrier.

Successful archive layout:

```text
checkpoint-id/
  epistemic/history.json
  epistemic/working.md
  epistemic/identities.json
  epistemic/boundary.json
  workspace/                    # complete copied task workspace
  workspace_manifest.json       # content, dirs and in-tree symlinks
  manifest.json                 # archive file hashes
  binding.json                  # E/X identities, hashes, boundary, status
  complete.json                 # final seal
```

The identity object must contain task and source identities plus SHA-256
identities for system prompt, seven-tool schema and effective model config;
continuation prompt SHA-256 is supplied when one exists, otherwise null. The
History prefix is saved in canonical UTF-8 JSON, with its byte hash. The
boundary includes review/request IDs, public cursor, task turn, and exact
completion/control state supplied by the caller. `verify_checkpoint` checks
the stored bytes, manifests, binding and optional expected identities only.

No restore, resume, replay, transition execution, semantic transport, verdict,
ground store, model-visible metadata or automated capture trigger is provided.
The archive may contain private task content and must be handled as research
data, not automatically published.
