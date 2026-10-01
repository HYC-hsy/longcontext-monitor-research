**Task reference:** Implement `refresh()` method so it updates `self.rendered` to reflect current `self.title`. Demonstration in demo.py should run successfully.

**Current state:** Turn-zero initialization. The `refresh()` method exists but contains only `pass`. Demo.py shows expected usage: create view with title, call refresh(), check rendered output, change title, refresh again, check updated output.

**Material requirement:** When `refresh()` is called, `self.rendered` must be updated to reflect the current value of `self.title`.

**Gap:** Implementation not yet attempted. No evidence of what the task agent will propose or whether `self.rendered` will correctly reflect title changes after refresh calls.

**Next:** Wait for task agent to begin implementation, then verify the refresh method actually updates rendered text to match current title.
