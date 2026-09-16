# PMA 维护控制意图自然交接：工程完成，待真实验证

日期：2026-09-17。用户授权先修协议摩擦，真实实验前停止。
父版本：155eb9b2236f1c67cc3754cb7909c4247fc1c28e。

## 依据与本轮范围

R8 的维护阶段三次尝试 intervene 被拒，另有六次 wait 被拒。模型已有控制意图，却只能通过维护结束标记进入下一阶段。此前时序审计另发现错误的完成叙述先于压缩，因此本步不改压缩或判断依据机制，单独修阶段衔接。

证据：PMA_FUSED_R8_TRAJECTORY_AUDIT_20260914.md、PMA_R8_COMPACTION_TEMPORAL_AUDIT_20260917.md。

## 改前与改后

改前：维护中控制调用 → Tool unavailable in this phase → 模型重复尝试/重新组织 → maintenance_complete → 判断。

改后：维护中控制调用 → 明确的未执行意图回执 → 结束维护 → 作者 process 用更新后的 bank 构造判断输入 → 同一监察者确认、修订或放弃意图 → 判断阶段控制工具才执行。

- 不新增工具。维护阶段暴露已有 intervene/wait/allow_complete 的相同参数，但说明其在本阶段仅交接提案。
- 无控制意图时，原 `<maintenance_complete/>` 结束方式仍有效。这是正常维护路径，不是历史兼容回退。
- 交接的 payload 保存原调用名及参数，不靠自然语言关键词推测动作。
- 阶段交接结果带 executed=false、input_sent=false；loop 保存这份结果，而不只保存泛化的 accepted。
- 仅判断阶段执行 host dispatch。维护中的 wait 不恢复任务/设置唤醒；allow_complete 不批准完成；intervene 不发消息。真实执行继续经过原有根提议有效性、去重与回执逻辑。
- 判断阶段收到明确的提案正文和“尚未执行”说明，可马上确认，也可修改或放弃，不要求为切换阶段重新调查。
- pending intent 只属于当前 FusedTransport/review；异常不自动提交，也不在下次唤醒自动重放。历史仍留有未执行回执。
- 同一响应中，交接前 bank 操作正常落盘；交接之后的批量工具调用按既有 loop 规则标为 not_executed。提示要求先提交所需记忆更新，判断阶段仍可修订 bank。
- 两阶段共用原调用预算。交接不增加第三阶段；预算不足/模型失败显式报错，不伪装为 wait 或成功。

## 作者代码保持与适配边界

上游 https://github.com/yifannnwu/proactive-memory-agent，commit 89e5c0d6aadfe531a1aee42fd290d48be89973dd，Apache-2.0。

已重新读取 MemoryAgent.process、两阶段 prompt 构建及实际调用链。仍由作者 process 顺序调用维护、判断，判断输入使用更新后的 bank；作者 bank executor、格式和解析保留。vendor 无改动，上游身份/行为测试通过。

本次是本地 FusedTransport 的输出协议适配，不是作者原有的控制意图交接机制，也不称原论文原样复现。未修改任务宿主屏障、follow/patrol、completion 生命周期、观察窗口、持续 History、记忆结构、压缩或语义判断原则。

## 改动文件

- GenericAgent-main/monitor_agent_core/pma_fused.py：阶段工具说明、临时意图保存与判断输入衔接、审计事件。
- GenericAgent-main/monitor_agent_core/loop.py：退出动作若有附加工具结果，将其保留在 history 回执的 result 字段；无附加结果的旧控制回执不变。
- GenericAgent-main/tests/test_monitor_pma_fused.py：更新维护权限测试，新增交接测试。
- AGENTS.md：新增本轮接线状态入口；不替换研究问题。

代码与测试累计 179 行增删（171 添加、8 删除），各开发步骤均小于 600 行。

## 验证

全部为本地确定性测试，不调用真实模型，不启动 Docker 任务。

1. fused 套件：25 passed。
2. fused、PMA memory/two-phase、上游 parity、provider 回执、独立性、completion settlement：50 passed、10 历史契约 skipped、3 subtests passed。
3. 扩展到 tests 目录全部 monitor/pma 名称测试：438 passed、20 skipped、3 subtests passed、9 failed。
4. 其中进程取消/清理的 4 项失败：沙箱外重跑相关套件，8 passed、1 skipped，未改 process_runner。
5. 另 5 项为 test_clean_monitor_runtime.py 旧 fixture 缺少 task_id/task_workspace；以内存载入父版本 loop/pma_fused 后重跑该文件，仍是相同 5 failed、5 passed。失败发生在运行时构造之前，与本次交接无关。本轮未修改旧 fixture，也不声称全套回归通过。
6. git diff --check 无空白错误；vendor diff 为空。

新增覆盖：更新 bank 进入判断；提案可修改/丢弃；维护不调用 host；根完成仍需有效提议；异常不发送/不重放；同批工具回执完整；共享预算；真实 provider 类的 history 序列化；工具描述不污染全局定义。真实 provider 测试替换网络请求，不是 API 连通性/效果验证。

## 剩余门禁

现在应运行同一道 Fyne 2.2 的协议修复候选，使用新 run-id，保持双方模型、预算、隔离与其他机制一致。启动前仍需用户确认和常规预检。本轮没有调用 API、启动/准备真实运行或变更凭据。

重点验收：维护控制调用是否不再遭阶段拒绝；提案与实际提交能否清楚区分；判断能否直接使用已有调查而不重复；完成有效性/并发跟进是否保持；调用、延迟和成本变化。不能预设模型一定会有效使用本接口。

本轮不实施 Judgment Record/Decision Basis，也不宣称修复了不充分证据导致的错误完成。协议基线通过后再单独验证该机制。无需专家再次裁决才能进行此项协议验证。
