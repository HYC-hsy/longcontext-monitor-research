# Stage 1 zero-model preparation audit

- Fixture source: `570356ced6ccc5d213c2bd49d7af15c51178039d`
- Plan: `PLAN.json`, 54 not-started logical decisions
- Plan SHA-256: `1673e6cc3ec1f7840dcba0145d13bb5ec1339b04fe7761ba09d9fd29058109e7`
- Profile name: `claude_monitor_opus48`; expected configured model: `claude-opus-4-8`
- Preparation-time private profile file SHA-256: `cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1`
- Preparation-time non-secret profile facts: Anthropic Messages, temperature 1,
  adaptive thinking, max_tokens 8192, max_retries 8, route `monitor`.
  A later execution must re-check and bind the then-effective private file;
  these preparation facts are not an execution authorization.
- Independent execution authorization: **absent**
- Provider/model calls: **0**

Offline commands from `E:\longcontext-cqs-v0-20261005`:

```text
D:\python\python.exe method_discovery\constitution_panel_v1\stage1_plan.py --repo E:\longcontext-cqs-v0-20261005 --output E:\longcontext-cqs-v0-20261005\method_discovery\constitution_panel_v1\stage1\PLAN.json
=> 1673e6cc3ec1f7840dcba0145d13bb5ec1339b04fe7761ba09d9fd29058109e7

D:\python\python.exe method_discovery\constitution_panel_v1\stage1_runner.py
=> {"status": "offline_identity_audit_only", "planned_logical_calls": 54, "fixture_commit": "570356ced6ccc5d213c2bd49d7af15c51178039d"}

D:\python\python.exe -m pytest method_discovery\constitution_panel_v1\test_panel.py method_discovery\constitution_panel_v1\test_stage1.py -q
=> 33 passed in 14.41s; process exit code 0
```

The pytest process also emitted a Windows `PermissionError` while cleaning an
old pytest temporary directory in `atexit`; the tests had completed and the
process returned zero. Stage 1 tests used a local fake SSE response and a
synthetic first-attempt timeout. This is transport plumbing evidence only, not
a scientific trial or model behavior evidence.
