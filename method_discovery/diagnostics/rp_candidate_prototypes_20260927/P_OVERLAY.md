# P overlay — bounded short-path comparison

When an important observation has a real choice among executable paths, the
same Supervisor may briefly compare at most two paths. Each path may contain
at most two necessary ordinary actions. Compare which possible outcomes could
change the current decision and the cost/latency of the path, then execute the
first action of the selected path. After its result, reassess; do not enumerate
paths when one action is already sufficient, and do not add a fixed call.

Navigation, entry-point location, and environment confirmation may be the first
action. Waiting for a currently running Task Agent validation is allowed.
Output tokens, tool time, provider attempts, and task waiting are costs. This
overlay adds no selector tool, Agent, planning stage, private-thought export,
or runtime semantic judgment.
