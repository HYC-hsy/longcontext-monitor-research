# Startup failure record

The terminal invocation of the frozen single-slot launcher exited with code 1 during `runner.run_proof -> preflight -> m4.resolve_model`. The Docker identity probe imported `agentmain.GenericAgent` from the read-only mounted source and failed in its constructor:

```text
File "/opt/genericagent/agentmain.py", line 98, in __init__
    os.makedirs(os.path.join(script_dir, 'temp'), exist_ok=True)
OSError: [Errno 30] Read-only file system: '/opt/genericagent/temp'
```

The fresh Git archive source lacked the untracked runtime `temp/` directory that existed in the earlier private source. `tree_hash(ga_mode=true)` excludes `temp/`, so source SHA checks did not reveal the missing directory. The launcher did not proceed to a Task trial, inference bridge send, or native evaluator. No directory was added and no retry was attempted in this slot.

The terminal's full PTY transcript was not written to a file by the launcher; the excerpt above is transcribed from the captured terminal result. No raw Task/Supervisor trajectory exists for this failure.
