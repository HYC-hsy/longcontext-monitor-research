Turn-zero initialization complete.

**Task requirement:** Maintain the request dispatcher with public `handle` function that uses configured route and returns selected handler's response. Workspace includes runnable demonstration.

**Current state verified:**
- dispatcher.py: Public `handle(path)` function resolves via wiring.resolve() and returns handler()
- wiring.py: ROUTES configuration {'/': home} with resolve() lookup
- demo.py: Demonstration runs successfully (outputs "home page" / "not found")

All explicit requirements appear satisfied. The implementation is functional and complete against stated task.

**Decision reference:** Patrol assessment - no Task Agent activity yet (no synopsis/events at cursor 0).

No material discrepancy identified at initialization.
