Task requires request dispatcher with public `handle` function using configured route to return selected handler's response. Explicitly requires "workspace includes a small demonstration that can be run locally."

Current material gap: demo.py cannot run - produces ModuleNotFoundError when importing dispatcher. Verified by execution attempt in workspace directory.

This contradicts the explicit local demonstration requirement. Resolution requires demo.py to execute successfully from workspace, producing output from handle('/') and handle('/missing') without import or runtime errors.
