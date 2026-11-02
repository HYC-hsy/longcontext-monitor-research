CURRENT ENGINEERING FIX: DELETE_INTERFACE_FIX.md; source 55e5a3122720e4502dcad28f8b71c7c0f33ff5ce. Latest offline result: 81/81. Read/delete share displayed-memory scope and avoid alias reinterpretation. SYSTEM only adds STATUS to an already-supported parameter list. Earlier reports/counts below are historical.

# 离线验收

最终源码提交 afc14c3a3b714bc9b1f19b28a36cb3097a94b85d，测试代码树 bc5803ec59b2c0e176885b8b90f014a917d63cbe。六个改动源码/测试/runner 文件已在该 SHA 逐一远端回读，原文一致。Git CLI 无凭据，改用已连接 GitHub 上传，再拉回本地；未 force-push，未触碰 DMS 工作区。

```sh
PMA_TEST_STRICT_IMPORTS=1 LITELLM_LOCAL_MODEL_COST_MAP=True <EXISTING_PYTHON> -B pma_evidence_review/tools/run_p1_source_checks.py --source-links-context --report <NEW_REPORT_JSON>
```

69 tests，0 errors/failures/skips，14.910 秒；报告 exit_code=0。沿用已有真实依赖环境和网络守卫，没有缺包替身。旧 58 项加新 11 项；原始结果在 /tmp/context-check-budget-final.{json,stdout,stderr}。公开 offline-checks.* 仅替换工作区/依赖根路径，原始字节哈希保存在 IDENTITIES.json。

|边界|验证|
|---|---|
|A+B 摘要只选 B|sources 无 A；context 包含 A 并逐字等于冻结 prompt，新窗口出现后仍不变|
|源与上下文分离|legacy sources 返回未关联，context 单独返回冻结输入；缺选中事件不会阻断有效 context|
|冻结身份/完整性|活动内容、task、cycle、窗口字节/hash、缺失/损坏拒绝；无窗口 page_sequence_complete=false|
|游标|双向跨 view、跨任务、跨条目拒绝；旧来源快照与别名冻结检查继续通过|
|长文本|长 Unicode、CRLF、制表符、嵌套 JSON/反斜线逐字拼回；每页 encode 后 ≤8000 Unicode chars|
|预算/续轮|两视图共同四读；最多两续轮/三次逻辑调用；第三轮实际 schema write-only|
|候选隔离|旧实际 system/schema 与归档相等；旧六例输入/hash 不变；默认 source-read 旧回归通过|
|身份/收集|新模块进入 62 文件实际 source_identity，删除/改字节拒绝；新测试进入显式检查入口|
|运行接线|新候选六例 in-process fake client 与固定源码实际 CLI 均完成；每例一次 no-op 假调用|

SCRIPTED_CLI.json 记录固定源码 CLI 的每例输入 SHA、system/schema/prompt SHA、62 文件一致性和终态；原件保留 /tmp/context-scripted-cli-final。没有读取真实 profile，没有真实 provider、Task、P2、eval，也没有重跑旧真实组。旧 client adapter 回归仍以合成 profile/fake provider 跑通。

开发第一轮 64 项中一项新增夹具把 observation 直接传成 dict，现有投影不接受，改为实际支持的 JSON 字符串后通过；未放宽实现合同。之后补齐身份/游标检查，最终 69/69。

未覆盖真实模型选择/消费质量、语义结论是否改善、在线长程收益、P2 集成、并发写入、通用外部窗口迁移。context 只返回生成时实际可见 prompt，不返回存档中非展示的 raw_generation_context。即使完整分页读完，也没有证明摘要正确；有些窗口超出本轮预算仍需明确未读。

最终核查还修正 runner 的预算元数据：曾误记默认候选 2/1，现与实际 linked 执行一致为 4/2，新增配置断言。修后复验遇到 sparse checkout 缺既有身份 helper 模块；补齐已跟踪源码后最终 69/69。中间失败记录保留 /tmp/context-check-budgetfix*，未放宽测试标准。

## Independent-review regression addendum

Parent: c919d0b069bc4b957e03e338e5a3515f3cc42051. Only 46 test lines added; no implementation or runtime-source changes. Same --source-links-context entry point: 71 tests, 0 errors/failures/skips, 14.966 seconds, exit_code=0. New public reports: review-addendum-checks.*; raw reports: /tmp/context-check-review-addendum.*. IDENTITIES records original hashes. Earlier 69-test offline-checks.* remains historical evidence.

- r0 reads E1; r1 saves a knowledge entry and reads E1; r2 saves another entry. Each saved entry's paginated context equals its exact actual r1/r2 prompt, including serialized prior calls and receipts, and differs from r0.
- With recomputed valid window hashes, wrong cycle_id, mismatched archive.task text, and a non-string model_input each return source_binding_error.

No real profile/model, Task, P2 or eval. No separate CLI rerun because all 62 runtime sources remain unchanged; the suite retains existing six-case fake-client checks. Earlier SOURCE_REMOTE_READBACK.json records the six-file snapshot at afc14c3; this addendum changes its test file only. Final delivery SHA will be read back separately.
