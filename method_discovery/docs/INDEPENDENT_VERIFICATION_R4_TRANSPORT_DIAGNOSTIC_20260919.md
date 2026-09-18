# R4 C/D transport diagnostic — 2026-09-19

This is a connectivity/measurement record, **not** a C/D mechanism result.
The frozen r4 fixture and confirmed-label default panel were used. Toolbar
and Desktop were excluded. No full long task was run.

| Local run directory | Cases/groups recorded | Completed | Execution errors | Transport attempts | Tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| `run_r4_cd_20260918` | 10 | 0 | 10 | 90 | 0 |
| `run_r4_cd_retry_20260918` | 3 | 0 | 3 | 27 | 0 |
| `probe_single_retry_20260918` | 1 | 0 | 1 | 9 | 0 |
| `probe_single_retry2_20260918` | 1 | 1 | 0 | 2 | 10,155 |
| `run_r4_cd_final_20260919` | 3 | 0 | 3 | 27 | 0 |

The sole completed run was `app_metadata_defaults` under C:
`supported_in_scope`, two logical calls and two transport attempts. It proves
that this path can finish once; it is not a replicated or paired C/D effect
result. The other recorded groups ended with `RetryableProviderError`, with
`ConnectionError` on their transport attempts. Their `score_eligible=false`
and `correct=null`; they must remain in reliability denominators, not in an
accuracy comparison. The panel processes were stopped after repeated failures
instead of attempting all nine eligible cases. These run directories are local
and are not promoted to the expert evidence panel.

The provider's actual `/v1/messages?beta=true` streaming endpoint returned
HTTP 200 and `message_start` in a minimal probe; a same-client one-tool probe
also succeeded. Therefore the credentials and basic endpoint are not uniformly
unavailable. The precise cause of the intermittent panel `ConnectionError`
remains unresolved; do not attribute it to C/D or declare the remote service
healthy for a full comparison from one short success.

## Counter correction

The old error-path `requests=0` in these local JSON files was the number of
*successful usage records*, not the number of logical attempts. Each failed
group actually attempted one `client.complete()` call, whose provider layer
made nine transport attempts. The runner now records the attempted logical
call separately from `successful_responses`, and a deterministic regression
checks this. Historical result files are not rewritten; interpret their
`requests` field with this caveat. No model call is needed to test this fix.

Next valid comparison requires a fresh output directory, verified provider
stability, C/D on the same confirmed cases, and a separate B subset. Do not
combine the single successful C trial with error-only D attempts as if paired.
