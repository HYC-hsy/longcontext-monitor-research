# 本轮离线验收

源码 f6a3982b73d4c7d657242cba4e6c0f3073848ff5，完整 tree a4a85624adcb8266713e33bbc2c231c983e2d950，与本地测试源码 924a0a11 相同。GitHub 连接器只改变提交身份/时间；没有 force-push。

最终定向入口 `run_p1_source_checks.py --source-links-context`：**90 tests，0 errors/failures/skips，18.940 秒，exit_code=0**。沿用真实依赖环境及网络守卫，没有缺包替身。原始记录保留 `/tmp/context-history-release.{json,stdout,stderr}`，公开 offline-checks.* 只替换工作区/依赖根路径，原件字节哈希在 IDENTITIES.json。

|检查|结果与含义|
|---|---|
|旧候选边界|原 source-read/source-links-v1 检查通过，实际 system/schema 保持原样；原六例输入未改|
|默认读取|未指定 view、无选定来源时一读返回 context；显式 sources 不返回生成输入；损坏/声明了却缺失的来源不触发宽松回退|
|A+B 只选 B|目录自动保留当时可见 A 的 ref；旧 A 删除后仍可读到 manual_origin 原查询回执|
|冻结与可见范围|同 ID 换内容、当前预过滤不展示、状态重开后仍读旧快照；未展示活动 ID 不能借历史机制直接访问|
|handle 权限|未实际返回的不授予；跨任务、篡改、名字冲突拒绝；不可删除；合法 source_ids 引用可继承冻结 ref|
|分页|100 条目录原子分页，长 Unicode/CRLF/引号/反斜线原文逐字拼回；整页 JSON ≤8000 字；cursor 不能跨目标或请求视图重放|
|预算与多轮|活动/历史读共享四次预算，三逻辑调用末轮 write-only；r2 保存窗口含实际 prompt、此前调用/回执及历史 handle 记录|
|legacy|来源缺失如实 unrecorded/不关联；派生内容、输入目录和原文分字段，不冒充完整证据|
|身份/收集|63 项实际运行源码含新 helper；缺失/改字节拒绝；新增测试模块进入显式检查入口|

另做一次没有模型的 A04 实际可见调用回放和两次开发侧读取探针，摘要见 RECORDED_A04_PROBE.json。实际三轮名称/参数未改，默认两次读取均解析为 context，旧 RL3HYG6d 删除后仍可从新窗口目录读 origin_27 并验证哈希。原失败归档不覆盖。探针输出目录含内部签名密钥，仅本机保留，未整体发布。

工程分两步：第一步 274 行增加、5 行删除（helper/底层可选扩展与定点检查）；第二步 330 行增加、43 行删除（A 接入、GAP 与集成回归）。每一步均小于 600 行；本目录报告/schema/清单是生成或说明材料，不计为新增机制代码。

没有真实 profile、真实 provider、Task、P2、eval 或旧真实组。既有 client adapter 检查仍使用合成 profile/fake provider。测试证明接口与数据链条，不证明模型会正确理解、选源、修订或带来语义增益；大窗口也不保证在两次串行续读内读完。
