# Policy/entry wiring offline verification

Base: 57b204aefeaf3768b47a698dabde3a7880a93f49. Python 3.12.14.
292 tests: PMA 276 + real pinned native Harbor 16; zero errors/failures/skips.
Original 282 test IDs retained. Ten new tests are host-only preflight/entry wiring regressions.
Actual prepare -> plan -> manifest -> identity/config hash is tested with synthetic local task/profile/image boundaries;
this does not claim a new native Harbor lifecycle. No Docker, real model, real Task or evaluator execution.
The production hook runtime policy checks, gate semantics, one-sentence prompt, original 29 benchmark and frozen labels are unchanged.
Raw runner reports/logs retain cloud paths and actual loaded Harbor origins; Windows and native fixture recertification remain pending.

Changes: reject missing/non-object gap policy before output/profile/grant/runtime;
correctly persist gate into actual prepare plan; reject returned manifest gate mismatch;
remove the misplaced undefined gate reference from stateful fake preparation.
Handoff exports only requested policy from two fixed historical Git identity objects and passes it only to B.
The original failed fixture/unknown cleanup record is not rewritten or relabeled.
