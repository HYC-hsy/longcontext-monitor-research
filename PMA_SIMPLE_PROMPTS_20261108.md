# PMA concise prompts: approved trial candidate (2026-11-08)

## Scope

Exact parent: `b17151b8d57c61cfb4e058ad1601225f9fa2ea15`.
Only the read-context P1 and shared predictive P2 system text change in production.
The rejected detailed evidence-audit prompt revision is not included.

P1 still selects information expected to be useful within the next 10 turns.
The added fidelity instruction preserves meaning and degree of certainty without
mandating information categories, evidence records, fixed fields, or banning
useful hypotheses and suggestions. P2 remains selective and defaults to no
intervention. It permits grounded synthesis and suggestions while preserving
uncertainty. Existing runtime templates, output tags, `memory_add`, required
`memory_read({"bank_id":"knowledge"})`, initial call, eight-new-step cadence,
continuous histories and GA trimming, model settings, budgets, and input
projection are unchanged. No SAM-style source-page retrieval is introduced.

P2 is a shared constant: Predictive, ContextPredictive, and ReadContextPredictive
variants receive this new P2 text. Only ReadContextPredictive P1 changes. The
upstream original MemoryAgent is unchanged. The intended trial method is
`pma-predictive-read-context` (condition B, `pma_predictive_read_context_v1`).

## Actual P1 system text

```text
You organize information from the task execution.

Based on the task description and the task agent's trajectory, organize and save information expected to be useful within the next 10 turns. When organizing information, preserve its original meaning and degree of certainty.

Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge".
```

## Actual P2 system text

```text
You help the task agent complete its task by reminding it of relevant information from memory at appropriate times.

Review the memory bank alongside the task requirements and the agent's recent trajectory, and decide whether any information can help its current work. You may synthesize information, identify connections, and offer grounded inferences or suggestions; preserve the information's original uncertainty when expressing them.

Default to no intervention. Do not intervene if no reminder is needed now, or if the relevant information is already visible in the recent trajectory and the agent's actions indicate that it has taken it into account. Do not take over the task agent's work.

If a reminder is needed, write:
<context_for_action>
Relevant information to bring to the agent's attention.
</context_for_action>

Otherwise, write:
<no_intervention/>
```

## Verification

The independent local test projection has 211 baseline files, all checked against
the pinned parent's Git blob identities before editing. Publication overlays only
the listed changed files onto the parent's FULL tree; the local projection history
must not be published. The two production ASTs are identical except prompt values.
Tools and dynamic user templates remain unchanged.

Selected offline regression: **265 passed, 156 subtests passed**, with three
existing Pydantic ReadOnly warnings. Actual Harbor LiteLLM to Anthropic request
conversion asserts exact full P1/P2 text, with synthetic provider responses and
network disabled. Compileall passed. This is not a claim of model adherence,
Windows acceptance, or task benefit; no live model or Docker task was run here.
The first new fixture run had one failed assertion because the reused Script
fixture always returns no_intervention in P2. The fixture was corrected to provide
a synthetic reminder and the entire selected suite rerun successfully; no runtime
code was changed for that fixture failure.

Reproduce with existing test dependencies:

```bash
STAGE=method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013
export PYTHONPATH="$STAGE/vendor/pma_89e5c0d/src:$STAGE/vendor/pma_89e5c0d/external/harbor/src:$STAGE:GenericAgent-main:experiment_runner:.:$PYTHONPATH"
export LITELLM_LOCAL_MODEL_COST_MAP=True
python -m pytest -q tests experiment_runner/test_context_predictive.py experiment_runner/test_runner_frontend.py experiment_runner/test_runtime_policy.py experiment_runner/test_runtime_compatibility.py experiment_runner/test_policy_evidence.py experiment_runner/test_runtime_integration.py experiment_runner/test_runtime_reuse.py experiment_runner/test_dataset_catalog.py experiment_runner/test_export_ga_visible_audit.py experiment_runner/test_evaluation_cache.py
python -m compileall -q tests "$STAGE/vendor/pma_89e5c0d/src/memory_agent/memory"
```

## Two-task developer trial

Use the new exact publication commit, not branch HEAD after later changes. Run
rstan-to-pystan then nginx-request-logging, once each, with fresh empty banks,
histories, run IDs and environments. Do not reuse a previous result or retry a
reward-zero trial. Preserve the previous GA20 bank-ID profiles and effective
model/provider settings. Dataset stays `2fd12b88aafdd04a52c298e3940bcb189f9766d6`;
Harbor stays `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`.

Use the existing unified runner, not the old standalone launcher:

```bash
python -m experiment_runner run --config <private-local-config.json> --method pma-predictive-read-context --task rstan-to-pystan --task nginx-request-logging --output <new-output-directory>
```

The config must bind all source/runtime paths to this exact code. Keep serial
execution and runtime_policy agent_timeout=uncapped, task_turns=uncapped,
verifier_timeout=official. Reuse and verify the established evaluation setup;
do not silently change models, dataset, runtime, or evaluation to unblock a run.
Verify actual prompt text, method binding, source identity and effective limits
before real calls. Execute using a genuine user-visible background terminal,
not an unrelated observer loop or an unsupported claim based on session_id.

After each task, run native evaluation and clean only its owned resources.
Archive actual visible trajectories, P1/P2 request/response content, bank contents,
read tool receipts, reminders linked to subsequent actual provider attempts,
evaluation, effective configuration and cleanup evidence. Public archives must
omit secrets/private configuration/hidden tests without changing runtime inputs.
Count calls and tokens only where evidence exists; unknown cost stays unknown.
Compare the corresponding b171 GA20 cases as diagnostic, not a causal A/B result.
