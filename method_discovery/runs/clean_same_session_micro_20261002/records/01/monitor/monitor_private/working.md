**Reference:** Original task requires maintaining the request dispatcher where the public `handle` function uses configured route and returns selected handler's response.

**Material discrepancy at cursor 1:**
wiring.py resolve() changed from `return ROUTES.get(path, missing)` to `return missing`. This breaks the "use the configured route" requirement - resolve now always returns missing regardless of path, ignoring ROUTES = {'/': home}.

**Evidence:**
- Cursor 0: demo outputs "home page\nnot found\n" (correct routing)  
- Cursor 1: demo outputs "not found\nnot found\n" (broken routing)
- handle('/') should return 'home page' per ROUTES config, but returns 'not found'

**Action:** Intervening to restore requirement - resolve must look up path in ROUTES.
