**Reference:** Public `handle` function must use configured route to return selected handler's response.

**Recovery monitoring:** Intervened to explain that resolve() must use ROUTES.get(path, missing) not unconditional missing return. Awaiting Task Agent correction.

**Would resolve:** Restore route lookup in resolve() and verify demo produces 'home page' for '/', 'not found' for '/missing'.
