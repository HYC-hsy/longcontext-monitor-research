# P1 source-links-context-v1：冻结生成上下文入口

从固定 eb406f2a4b1cc74d8d4a34f21fe958d558fa0c4e 分出；与 DMS 候选独立，没有修改或合并其工作区。源码提交 b2bc53856863c971107fa02fc57aae60f142be33，交付提交只补材料。用户已授权本阶段修复与 GitHub 交付，未运行真实模型、Task、P2 或评价，未重跑旧真实组。

## 目的与接口

摘要可能综合旧记忆 A 和新事件 B，却只选 B 为 source_ids。本候选保留该选择作为重点定位，同时给消费者显式回看条目生成时的完整可见 **prompt/model_input**；包括当轮旧记忆、事件及已呈现续轮回执。它不返回额外 raw_generation_context，不把原始存储里未展示的内容追加成模型曾见输入，也不扩展到 system/schema 或任意历史文件。

显式运行 `--candidate source-links-context-v1`。仍只有 memory_read_source：

```json
{"memory_id":"STATUS","view":"context"}
```

`view` 可选 `sources` / `context`，默认 `sources`；继续读取时同一 memory_id、同一 view，原样传 next_cursor。memory/STATUS 可读绑定窗口；E/TASK 仍读 sources，context 返回 context_unavailable。sources 只返回选定/继承来源；legacy 未关联不再暗中混入 context，须显式切换。旧 source-links-v1 的隐式 legacy 行为、system/schema 保留，默认 source-read 也保留。

每页是完整 JSON，最多 8000 Unicode 字符，复用原字段分段分页/HMAC 游标。游标快照绑定任务、条目、绑定内容及 view；跨视图、跨目标、跨任务和内容变化会拒绝。context 读取只接受绑定窗口名与原始文件哈希，并校验 task、cycle_id、活动内容/类别及请求冻结 ref；绝不替换成当前窗口。缺窗口、损坏、来源缺失、legacy 没有绑定均显式返回错误/未关联，不放宽到路径读取。

新回执给出 view、available_views、scope、truncated、next_cursor、page_sequence_complete。available_views 表示已记录的绑定入口，实际读取仍校验文件存在和完整性。`context_complete` 仅表示该窗口页序结束。新视图 `complete=false`、`semantic_verification_performed=false` 始终明确未做语义核验；读完不是结论已被证明。sources 的 source_complete 也只是所选来源序列结束，不保证选全。

## 改动范围

- p1_source_links.py：在旧调用默认路径之外增加显式视图；复用冻结 ref/window 和原分页器。
- p1_linked_agent.py：实例 system 与 opt-in view 接口，原类默认值和写策略保持原状。
- p1_context_agent.py：19 行独立候选，只有一个新增提示段和 view schema。
- run_p1_source_case.py：显式候选路由，运行源码身份纳入新模块（62 项）。
- run_p1_source_checks.py：新增 --source-links-context，收集旧 58 项和新 11 项检查。
- test_p1_context_agent.py：冻结窗口、原文分页、边界、预算与真实请求接线的离线检查。

没有自动发现反证、UPDATE 工具、审稿/语义判定、树、额外模型阶段、调用、写策略变化或 P2 接线。参考 MAGE/SAM 的输入覆盖思路；直接复用本仓已有窗口，没有复制第三方代码。

## 验收与限制

69 tests，0 failures/errors/skips。A50+B200、只选 B 的确定性夹具：sources 不含 A，context 精确拼回生成 prompt 并包含 A。六个旧冻结输入通过新 runner 各一次 scripted no-op；只说明接线正常，不是语义改善。完整检查与边界见 TEST_RESULTS.md；Windows 离线入口见 HANDOFF.md；运行哈希见 SOURCE_IDENTITY.json，文件覆盖见 MANIFEST.json。

这轮只修消费者入口。可能仍有漏读、错误理解和过度推断；窗口可能超过四次读预算；完整 context 中也可能有旧错误。未验证真实模型效果、在线长程收益、P2、并发写入或跨版本历史迁移。工程通过不能替代之后另行授权的语义/真实验证。
