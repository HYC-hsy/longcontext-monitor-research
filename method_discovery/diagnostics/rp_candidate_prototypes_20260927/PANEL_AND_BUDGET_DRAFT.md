# Panel and budget draft — not frozen

Four situation families are retained:

1. local evidence is insufficient but a direct source observation can settle a
   local premise;
2. the preferred observation is unavailable and an ordinary replacement may be
   possible;
3. evidence is sufficient on a correct control and investigation should relax;
4. a local repair is followed by renewed whole-task judgment.

Compare M1 with R and P independently; do not combine candidates. A small
initial proposal is four situations × two independent repeats per arm. This is
not an authorization, equivalence test, or held-out evaluation.

For a future manifest, the following is a proposed starting budget, not a
freeze:

* at most 12 logical Supervisor calls per review and at most 2 reviews per
  record;
* at most 2 transport/provider retries per logical request, recorded
  separately;
* maximum 1,200 output tokens per logical completion;
* maximum 120 seconds per individual analysis tool operation;
* maximum 1,800 seconds per record wall time;
* Task-Agent wait/interruption time recorded separately, including elapsed wait
  latency and any correction delivery delay.

For a future manifest, each record should also specify:

* logical Supervisor-call ceiling per review and total review count;
* provider retry policy and attempts separately from logical calls;
* maximum input/output tokens and tool wall-time limits;
* total record wall time;
* Task-Agent waiting/interruption cost and wait latency;
* no online verifier/gold feedback.

These numbers are intentionally provisional. D1's six-call ceiling is not a
deployment invariant and is not copied. Any run must preserve the same M1
budget across arms, count planning output as cost, and retain incomplete,
unresolved, wrong-release, wrong-block, and infrastructure outcomes distinctly.
No record is rerun after its trajectory is observed. A systemic infrastructure
failure stops the panel for independent adjudication; valid model behavior is
not invalidated for being unfavorable.
