# Independent monitor host contract

This package installs independently with `pip install <this-directory>` and depends
only on Python and requests. Neither GA nor its credentials, GUI, evolution,
provider, telemetry or execution loop is imported. Repository placement does not
define runtime configuration: pass a profile file to load_profile or set
MONITOR_CONFIG_FILE. Load the profile and pass the configuration to MonitorRuntime.

## Host inputs

Supply public_task, a stable task_id, task_workspace, a fresh artifact_dir,
config_name/model_config and interrupt_callback. The host may supply
task_original_path: an existing path the Task Agent can actually read. The core
does not create files in the supervised workspace. File mappings and lifecycle
callbacks are host capabilities, not model reasoning rules.

The host publishes dictionaries with task_turn (monotonic progress counter), text
(unaltered public model text), synopsis (host-supplied chronological preview),
tool_calls (name plus original arguments), tool_results, and optional boundary and
provenance metadata. The adapter does mechanical field conversion; it does not
judge semantics. Original message and tool contents must not be omitted. The core
archives public_events.jsonl plus synopsis.jsonl: these remain two views, not an
extra semantic layer. Other frameworks implement this same contract.

archive_boundary publishes without waiting for model review. request_completion
is the separately controlled root handoff. interrupt_callback sends user-like
input; optional correction_begin/end perform the selected host wake barrier.
close ends the monitor process. The current GA adapter implements these callbacks;
the core itself never imports the task framework.

## Memory ownership

The artifact directory records task_id, original-task digest and workspace.
Mismatching identity or unidentified old artifacts fail before history restoration.
Resume uses the same identity and preserves archive sequence numbering. A new
task requires a new identity and directory. Simultaneous ownership of one artifact
directory is not supported; hosts must not launch duplicate owners.

The monitor's subprocess and history are independent of the task model, but its
life is managed by the host. Shared-container deployment is not a security boundary:
general code execution has the process's OS permissions. Stronger OS isolation
is separate from framework independence and must not be claimed here.
