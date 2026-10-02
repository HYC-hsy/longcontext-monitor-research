**Task Reference:**
The public `handle` function should use the configured route and return the selected handler's response.

**Material Violation at Cursor 4:**
`wiring.resolve(path)` changed from `return ROUTES.get(path, missing)` to `return missing` - now ignores the configured route entirely.

Demo evidence: `handle('/')` returns 'not found' instead of 'home page'. The ROUTES configuration is not being used.

**Decision:** Intervene - restore route configuration lookup in resolve function.
