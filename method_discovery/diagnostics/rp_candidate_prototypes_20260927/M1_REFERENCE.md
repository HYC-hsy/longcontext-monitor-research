# M1 reference

Implementation: `746a695adac4325d6440941d384d543d1364fef9`.

Production source references:

* `GenericAgent-main/monitor_agent_core/agent.py`
  (`DCEC_SYSTEM_PROMPT`, `_active_working_context`, `_dispatch`, `review`)
* `GenericAgent-main/monitor_agent_core/working_context.py`
  (`dcec_working_context`)
* `GenericAgent-main/monitor_agent_core/process_runner.py`
  (`AnalysisSessions`)

`M1_REFERENCE_CONTRACT.txt` is the offline copy of the M1 system contract used
by the synthetic request harness. The prototype treats the existing M1
semantic contract, ordinary seven-tool surface, persistent history, bounded
`working.md`, and normal review request as the common baseline. It does not
copy or replace production source. The exact source commit and paths are the
identity; the synthetic request fixture in `build_requests.py` is only an
offline comparison harness.
