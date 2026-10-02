**Task Reference:**
Maintain the request dispatcher where the public `handle` function uses the configured route and returns the selected handler's response. Demo should run locally.

**Initial State (cursor 0):**
Implementation exists and works:
- `dispatcher.handle(path)` calls `wiring.resolve(path)` to get handler from `ROUTES` config
- Returns handler's response via `handler()`
- Demo runs successfully: `handle('/')` → 'home page', `handle('/missing')` → 'not found'

**Current Understanding:**
Requirements satisfied. No material discrepancy detected. Awaiting task agent activity to see what "maintain" entails - could be monitoring, enhancement, or addressing issues that arise.

**Decision:** Patrol - observe initial task agent behavior to understand maintenance scope.
