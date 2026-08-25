# M1 有界修复：真实任务前工程报告

日期：2026-08-25  
父候选：`4b3713b`（首次 M1 FBR 运行所用实现）  
状态：工程修复完成，尚未进行修复后的真实任务运行，不能标记为 accepted `m1`

## 修复依据

首次 M1 FBR 真实运行取得 native verifier `7/7`，但与历史 M0 的同分结果相比：

- 监察决策从 83 增至 153；
- HOLD 从 11 增至 34；
- Agent 执行时间从约 69 分钟增至约 115 分钟；
- 语义工作区最终审计发现大量同义根义务、局部测试缺口晋升为根义务，以及每轮重写造成的正反馈；
- 运行最终因 monitor provider 余额不足结束，虽然事后 verifier 仍为 1.0。

因此这次修复不增加新论文机制，只修正创新 A 的当前实现：保留跨目标恢复、局部/全局区分和 UNKNOWN，同时移除状态身份漂移、无界投影与逐轮语义自激。

## 已实现修复

### 1. 稳定且可恢复遗漏的根义务身份

- 根义务使用源顺序稳定 ID：`obligation:0000`、`obligation:0001` 等。
- 已存在义务的 ID 和原文不可被后续释义替换。
- LLM 的普通 `workspace_delta` 不得创建 `root_contract` 或 `root_obligation`。
- 测试缺口、失败 patch、fixture 搜索和临时诊断只能留在 episode-local 状态。
- 不是绝对冻结首轮列表：若监察者重新阅读原始任务后，在专门的 `root_obligation_audit` 中恢复了首轮遗漏，允许单调追加；旧义务不能被删除。

这一区分同时防止 root explosion，并保留论文要解决的 representation omission 恢复能力。

### 2. 事件触发的语义写入

普通只读观察与未改变的 watch 不再持久化自由语义 delta。当前仅在以下公开边界接受语义写入：

- HOLD、ABSTAIN 或 RELEASE；
- 根任务 completion proposal；
- 公开写入、patch、代码执行或同类状态改变工具事件。

M0 的逐边界监察仍照常运行；门控只约束长期语义写入，不减少监察者对轨迹的可见性，也不改变干预决策。

### 3. 有界 routine active view

- 日常 prompt 不再嵌入完整历史 workspace，而使用单版本 active view。
- 所有根任务与根义务始终保留；局部对象按最近更新选取剩余槽位。
- 日常默认最多 48 个对象和 64 条关系；完整状态仍可通过 `read_semantic_workspace` / `search_semantic_workspace` 主动重建。
- durable checkpoint 只保存工作区指标，不再第二次复制完整工作区。

这保持了“语义状态 + 可检索历史 + 主动重建”的能力，同时去掉 prompt 中的重复全量状态。

### 4. Agent/monitor 精确用量分账

- 每个 provider request 标记 `call_type=task_agent|monitor`。
- provider 返回的原始 usage、输入 token、输出 token、缓存创建和缓存读取 token 写入统一 research event。
- usage event 与 `llm_call_id` 和 provider request event 关联。
- 现有 OTel usage 路径保留，不发生双套互斥埋点；research JSONL 补充研究需要的调用身份和归因。

对于流式 API，单次调用可能产生多个 usage snapshot；后续汇总必须按 `llm_call_id` 和 provider 语义去重/组合，不能机械把快照全部相加。

## 离线证据

将上一轮 `live_10m/m1_workspace_events.jsonl` 的 13 个历史自由 delta 输入新工作区：

- 历史事件：23；
- 重放 delta：13；
- 仅由自由 delta 产生的根义务：0；
- 最终对象总数：10；
- 拒绝的根层写入：1；
- 无效行总数：3。

产物：`live_10m/bounded_offline_replay/`。该重放只证明结构防线按设计工作，不具有方法晋级权。

## 验证

- GenericAgent 全套：`221 passed`。
- long_context_bench 全套：`299 passed`。
- M1 real-run manifest：`3 passed`。
- `py_compile`：通过。
- `git diff --check`：通过；仅有既有 Windows CRLF 提示。
- 新 manifest：8 个 `prepared_not_executed` 分支，无在线 checker，无密钥。
- 当前 GenericAgent source SHA-256：`2e989a2036ab2b97800f42fec19c84306d04363e11c317312719fd2f4c6bc1fa`。

## 防漂移核对

- 服务创新：A（Dual-Layer Evidence-Carrying Task State）的声明式/过程工作区实现。
- 在线信息：只使用公开任务、Agent 行为、工具结果、工作区和历史；没有 native verifier 或隐藏测试输入。
- M0 关系：M0-v1.1 仍是母体和回退点；M1 开关关闭时控制路径保持不变。
- 研究问题：没有改成 completion checker、PMA 升级或单纯 prompt 字段工程。
- 收敛原则：该版本仍是待真实任务证伪的工程候选，不因单元测试通过而接受。

## 真实运行门禁

下一步才是修复后 FBR treatment 真实重跑，并与历史 M0、首次 M1 同任务轨迹比较。必须观察：

1. 是否保留首次 M1 的跨目标遗漏恢复；
2. HOLD、决策数、wall time 和 monitor token 是否显著回落；
3. 根义务是否保持稳定且不发生局部问题晋升；
4. 是否仍能纠正错误 oracle 与 unsupported closure；
5. native verifier 是否维持 7/7；
6. 是否在两小时与预算内自然结束。

在该真实任务结果出现前，不提交 `m1` accepted 标签，也不进入 M2。
