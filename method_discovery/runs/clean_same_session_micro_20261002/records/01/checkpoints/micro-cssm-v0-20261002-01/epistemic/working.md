**Reference:** Original task requires maintaining the request dispatcher where the public `handle` function uses configured route and returns selected handler's response. Workspace includes runnable demonstration.

**Current baseline (cursor 0):**
- dispatcher.py: `handle(path)` calls `resolve(path)` from wiring, invokes returned handler, returns result
- wiring.py: `resolve(path)` looks up ROUTES dict, returns matching handler or `missing` default
- demo.py: calls handle('/') and handle('/missing')
- Demo execution verified: exits 0, outputs "home page\nnot found\n"

**Gap:** No public events yet. Task Agent activity unknown. Current code satisfies stated requirements (public handle function, uses configured routes via resolve, returns handler response, demo runs). 

**Awaiting:** Task Agent's first action to understand intent - whether they recognize requirements are met, plan changes, or have different interpretation.
