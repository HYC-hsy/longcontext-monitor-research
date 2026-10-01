# Controlled Transition Fixture v0

Offline research instrumentation only. It takes a verified epistemic
checkpoint and applies one researcher-specified file-content bundle to an
independent copy of its task workspace. It does not restore or continue either
Agent and does not invoke WTV. The fixture records path/content facts only;
WTV remains responsible for its own later workspace samples.

## Interface

`apply_transition_fixture(checkpoint_dir=..., transition_source=...,
transition_id=..., expected_source_sha256=..., expected_checkpoint_id=...,
output_root=...)`

The caller supplies the preregistered SHA-256 of the **raw bundle file**. The
bundle is one JSON file:

```json
{
  "schema": "research-content-patch/1",
  "checkpoint_id": "checkpoint-1",
  "transition_id": "transition-1",
  "operations": [
    {"op": "write", "path": "src/example.go", "before_sha256": null,
     "content_base64": "bmV3Cg=="}
  ]
}
```

`write` with a null before hash adds a file; `write` with a SHA-256 replaces
exact existing bytes. `delete` requires an exact existing-file before hash and
has no content. An empty `operations` list is a valid no-transition control.
Only regular files can be patched; paths are normalized relative POSIX paths,
cannot traverse symlinks or `.git`, and cannot overlap. The input bundle is
copied verbatim into the research archive. Its source hash is checked **before**
any operation. No source-file discovery, patch generation, semantic choice or
automatic repair is performed.

## Boundary and artifact

The fixture first calls `verify_checkpoint`, checks its ID, copies only the
checkpoint workspace to a new, exclusive output directory, and compares the
copy's full manifest with the checkpoint's sealed manifest. It then checks all
file preconditions and writes `start.json` before applying operations. It
records each completed operation, generates the after manifest, verifies the
original checkpoint again, and writes `end.json` with `complete` status.

```text
transition-id/
  transition.json        # ID, source hash, before/after manifest hashes, status
  transition_source.json # exact researcher-provided bundle bytes
  source_hash.json       # expected/actual source SHA-256 and equality
  before_manifest.json  # verified X_t copy
  start.json             # marker before first mutation
  workspace/             # independent X_(t+1), including partial failures
  execution_log.jsonl    # completed file operations only
  after_manifest.json   # actual state, also best-effort on failure
  end.json              # complete or failed with reason
```

Any exception marks the attempt `failed` and preserves its copied workspace,
completed operation log and available after manifest. A failed or completed
transition ID cannot be overwritten or silently retried. An absent start marker
means failure occurred before mutation. The fixture does not promise an atomic
multi-file patch; partial results are preserved as failure evidence.

The synthetic tests include endpoint-like single-file changes, multi-file
option/wiring changes, validation-only changes and an empty transition. Those
case names exist only in test code, not in the output artifact or model input.

No model-visible checkpoint or transition metadata, replay, resume, Task Agent
continuation, native verifier, semantic transport, relevance label, dependency
graph or patch recommendation is provided. Archives may contain task source
and must be reviewed before publication.
