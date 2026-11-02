# 本轮离线验收

最新源码 26ff924d083616c5b6c91136b6ee6af312f8f83c，完整 tree af2a4c283017260a697ddd741d2db112532a7735。该 tree 与在 6c00dc5c 上测试的四文件引用补丁完全一致。此前 f6a3982b 与本地 924a0a11 相同的结论仅指初版历史入口源码；本次已叠加独立来源可用性及明确引用修复。没有 force-push。

最终定向入口 `run_p1_source_checks.py --source-links-context`：**95 tests，0 errors/failures/skips，20.785 秒，exit_code=0**。沿用真实依赖环境及网络守卫，没有缺包替身。原始记录保留 `/tmp/context-history-cited-release.{json,stdout,stderr}`；此前 90/93 项记录另行保留。公开 offline-checks.* 只替换工作区/依赖根路径，原件字节哈希在 IDENTITIES.json。

|检查|结果与含义|
|---|---|
|旧候选边界|原 source-read/source-links-v1 检查通过，实际 system/schema 保持原样；原六例输入未改|
|默认读取|未指定 view、无选定来源时一读返回 context；显式 sources 不返回生成输入；损坏/声明了却缺失的来源不触发宽松回退|
|独立来源可用性|E8 完好时，context missing/hash bad/坏目录引用均不遮蔽 sources；清楚记录覆盖错误，不授予坏 handle；context 仍拒绝|
|A+B 只选 B|目录自动保留当时可见 A 的 ref；旧 A 删除后仍可读到 manual_origin 原查询回执|
|冻结与可见范围|同 ID 换内容、当前预过滤不展示、状态重开后仍读旧快照；未展示活动 ID 不能借历史机制直接访问|
|handle 权限|未实际返回的不授予；跨任务、篡改、名字冲突拒绝；不可删除；合法 source_ids 引用可继承冻结 ref|
|明确引用身份|r0 只得目录未读 H，r1 用 H 写 C 并删旧对象；C ref 原子持久化 cited_history_handles，目录首项直达同一 H，不依赖旧 active；legacy 仍 unresolved|
|输出/输入区别|引用元数据只写新 ref；逐字比较 before_request 冻结窗口与保存后字节，未回写生成前 input coverage|
|持久化故障|首次 grant 写失败保留 engineering_error 并停止后续操作；引用 ref 提交失败无幽灵 C/引用，先前提交保留|
|分页|100 条目录原子分页，长 Unicode/CRLF/引号/反斜线原文逐字拼回；整页 JSON ≤8000 字；cursor 不能跨目标或请求视图重放|
|预算与多轮|短 A06 形状真实 maintain fake：summary→H(A)→原回执→r2 write，只有两次读；长 origin 在第二读明确 partial。四次是总 read 上限，仅 r0/r1 两个串行读取轮，r2 write-only|
|legacy|来源缺失如实 unrecorded/不关联；派生内容、输入目录和原文分字段，不冒充完整证据|
|身份/收集|63 项实际运行源码含新 helper；缺失/改字节拒绝；新增测试模块进入显式检查入口|

初版 f6a3982b 另做了无模型的 A04 实际可见调用回放和两次开发侧读取探针，历史摘要保留在 RECORDED_A04_PROBE.json，不能冒充本次新源码探针。当前 95 项 suite 中同一实际三轮可见调用回放也继续通过。原参数未改、原失败归档不覆盖。探针输出目录含内部签名密钥，仅本机保留，未整体发布。

工程分两步：第一步 274 行增加、5 行删除（helper/底层可选扩展与定点检查）；第二步 330 行增加、43 行删除（A 接入、GAP 与集成回归）。每一步均小于 600 行；本目录报告/schema/清单是生成或说明材料，不计为新增机制代码。

后续独立复审窄修分别为 99 增/6 删（目录故障不遮蔽来源）和 123 增/15 删（明确引用身份与原子性）。仍未超过单步 600 行。GAP/status 是用户授权的语义分工调整，独立冻结于 GAP_STATUS.diff，不能将整轮说成只有工程协议变更；其语义收益仍待真实验证。

helper 的百页循环只是逐字传输/目录授权检查。真实 P1 不能串行读百页；sources 目录在大来源之后也可能本轮不可达。“只读”是不得改记忆内容，首次授予 handle 确有 grant 元数据写入，其失败必须保留工程错误。

没有真实 profile、真实 provider、Task、P2、eval 或旧真实组。既有 client adapter 检查仍使用合成 profile/fake provider。测试证明接口与数据链条，不证明模型会正确理解、选源、修订或带来语义增益；大窗口也不保证在两次串行续读内读完。
