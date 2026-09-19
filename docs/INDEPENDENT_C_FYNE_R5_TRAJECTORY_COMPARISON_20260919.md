# Fyne R5 Trajectory Comparison: What the Higher-Scoring Run Actually Did

This is a trajectory audit of the valid R5 C-off/C-on pair.  It is not a claim
that Independent C was effective: the C-on Supervisor exposed the tool but made
zero actual `independent_check` calls.

## Outcome and confounding

| condition | task-agent provider calls | monitor tool calls | monitor interventions | native result |
|---|---:|---|---:|---:|
| C-off | 90 | 55 reads, 9 patches, 6 code runs, 5 waits | 3 | 2/7 |
| C-on | 86 | 79 reads, 12 patches, 6 code runs, 12 waits | 2 | 5/7 |

The task-agent trajectories are not identical: C-on used four fewer model calls,
more output tokens, and a different sequence of implementation and repair.
Consequently the score gap is confounded by task-agent sampling and cannot be
attributed to C or to the mere presence of its tool schema.

## The high-scoring trajectory's useful behaviors

### 1. Early broad reconnaissance, then implementation

C-on grouped several initial reads and entered App Metadata implementation by
task turn 6.  C-off mostly performed one-file-at-a-time exploration, had an
early killed analysis process, and did not begin the first patch until roughly
turn 14.  This is not a reason to force a fixed batch size; it is evidence that
the Agent benefited from a coherent initial workspace model instead of a long
serial discovery prelude.

### 2. One concrete semantic correction changed behavior

C-on initially implemented `NewAllStrings` as string-membership checking.  The
Supervisor read the requirement and issued one precise correction: the API was a
validator combinator that must run variadic validators and return the first
error.  The Task Agent immediately rewrote the implementation, after which
the entire validation phase passed.

This is a good correction pattern:

> identify one requirement-level semantic mismatch, cite the observed code and
> the original contract, request the smallest repair, then let the Agent run
> its own verification.

It is not a generic “remind the whole task” pattern.

### 3. Completion-boundary re-observation caught a different defect

After the validator repair, C-on's Supervisor did not treat a plausible global
summary as sufficient.  It kept the completion boundary open because the
required `data/validation/all.go` path still differed from the specification.
The Agent corrected the path and the Supervisor then allowed completion.

This is independent of the validator correction and shows the value of a final
root-scope coverage pass after local repair.

### 4. More observation, fewer direct interventions

C-on issued more ordinary reads and waits but fewer direct interventions than
C-off.  The better trajectory was not “interrupt more often”; it investigated
more and intervened only at two high-value points.  C-off interrupted three
times (Metadata, missing implementations, Toolbar), yet still finished with
four failed phases.  The evidence favors selective, evidence-backed control
over a higher reminder frequency.

## The lower-scoring trajectory's failure pattern

C-off's corrections were individually plausible, but they arrived after a
longer, less coherent implementation path.  The run still failed App Metadata,
Menu, Widget/Container and Desktop phases, then the monitor allowed completion
after the Agent claimed all seven targets were done.  Thus the failure is not
simply “the monitor did not intervene”; it is a failure to connect:

1. the global task scope,
2. the current implementation evidence,
3. the result of the latest repair, and
4. the final completion decision.

The C-off run is a concrete example of why a correct local correction does not
guarantee a correct root completion decision.

## What we should learn for the method

1. **Independent C remains untested.**  The parent must actually choose it in a
   consequential uncertainty case before any C comparison is meaningful.
2. **The durable mechanism to preserve is evidence-driven selective control:**
   direct inspection when the parent can settle the issue, an isolated check
   only when an independent view would change the decision, and a completion
   boundary that re-covers root scope after local repair.
3. **Do not encode the observed high-scoring sequence as a rigid script.**
   “Read three files”, “always correct the validator”, or “always use C” would
   overfit this Fyne task.  The transferable rule is to form a coherent task
   view, seek discriminating evidence, correct a concrete semantic mismatch,
   and re-check the global completion claim.
4. **The next C experiment must make consumption observable without forcing it.**
   It should record why the parent chose direct inspection, chose C, or judged a
   child check unnecessary.  Otherwise a zero-call result cannot distinguish
   “C was not needed” from “the parent did not recognize when C was useful.”

No prompt, model, memory, scheduling, or budget changes were made by this audit.

