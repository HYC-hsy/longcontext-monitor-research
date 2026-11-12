# Results and limits

| Task | Run ID | Task steps | Wakes / manager responses | Successful add / read | Delivered reminders | Native tests | Reward | Cleanup |
|---|---|---:|---:|---:|---:|---:|---:|---|
| kv-store-grpc | `pma-5d2e7f08494c4bf8` | 12 | 2 / 5 | 2 / 1 | 0 | 5/7 | 0 | confirmed |
| reshard-c4-data | `pma-d0da105161e94f14` | 27 | 4 / 16 | 5 / 7 | 0 | 0/1 | 0 | confirmed |
| rstan-to-pystan | `pma-cbd8bab501cf4eaf` | 37 | 5 / 19 | 6 / 7 | 1 | 5/6 | 0 | confirmed |
| largest-eigenval | `pma-b37b38a326f74da5` | 24 | 3 / 9 | 2 / 3 | 0 | 3/3 | 1 | confirmed |
| filter-js-from-html | `pma-273434c72cf74c95` | 2 | 1 / 4 | 1 / 2 | 0 | 0/2 | 0 | confirmed |

The only `context_for_action` was at rstan wake after step 16. The assembled reminder about PyStan parameter names entered Task provider attempt 17, and that attempt received a response. The Task had already observed the parameter-name error and described the fix in its step-17 summary; delivery and adjacency do not establish adoption or benefit. Fourteen other wakes ended in accepted `no_intervention`. No parse/delivery failure is recorded. At eigenval's first wake, two attempted `file_read` calls were rejected because that tool was not available; the manager then recovered within the same wake and issued `no_intervention`. Those rejected tool calls are not successful reads and should not be hidden by the cycle-level success.

Concrete content issues remain visible. KV's initial bank says the generated protobuf files use hyphens, while its later bank states that the generated names use underscores; this is a corrected inconsistency, not proof the first save was harmless. Reshard's wake after step 24 saved a “Task Completion” entry based on sampled MD5 checks and a large-file test, yet the native verifier failed. This does not identify the hidden-test failure, but it shows why a self-reported completion entry cannot substitute for native evaluation. Rstan saved a sampling-equivalence conclusion after reducing samples; its native verifier had one failure, without enough public evidence to attribute that failure to this entry. Filter ended after only two Task steps, so a ten-step future-use claim has no complete observation window. None of these unfavorable outcomes was removed from the archive.

Compared with the prior `10fe` run (same task order), Task steps were `22/29/36/32/2` there and `12/27/37/24/2` here; native rewards were `0/0/1/1/0` there and `0/0/0/1/0` here. Prior runs delivered two reminders (KV and rstan); this run delivered one (rstan). The role wording, step organization and reminder criterion changed together, and the Task trajectories differ. Single runs do not isolate a prompt effect or establish stable improvement/decline.

Task total turns and duration were uncapped; each official verifier retained its task-specific limit. Task model profile SHA-256: `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e`. PMA profile SHA-256: `c568aac2b3042f852537a7302bae48e756bbaea74f732ff7e985298d7b2a98e6`. Request-side model configuration is retained in the visible records; the PMA response model identifier is absent. PMA usage and physical HTTP attempts are unknown, and no cost is estimated. The ZIP's private-source/public-projection hash map is in the external index.
