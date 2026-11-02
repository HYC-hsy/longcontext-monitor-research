# 复用与必要适配

官方论文：https://proceedings.mlr.press/v306/mi26b.html 。2026-11-02 官方匿名入口 https://anonymous.4open.science/r/DMS-C48C 返回 HTTP 401，代码不可取得；不声称仍是旧的 410。第三方 ychnSu/Darwinian-Memory-System-DMS 固定 e1e995f2d2623b5e0d16268c30beb3c80e900618 的完整文件树未见 LICENSE/COPYING/NOTICE，README 自称算法级复现，Agent 在 dms/androidworld_agent.py。本轮未复制第三方代码、未执行仓库外软件。

DMS 有事前 plan 的 precondition/goal、轨迹及结果元数据。我们没有事前 Planner；这是历史原文分组适配，不是完整 DMS 复现。未加入 utility、风险门控、淘汰、embedding、Actor、Verifier、回放或额外 LLM。允许失败／单步材料，不采用成功轨迹过滤。

复用本仓库 SourceLinks 的事件 ID、实际调用配对、来源排序、字段分页、游标、逐操作原子持久化；SourceArchive 保存实际请求／回执窗口；复用 LinkedSourceP1Agent 的最多三轮工具续答、_calls、日志、usage 和预算。只是文本忠实续接，不冒称原生 messages 工具续轮。

新增 p1_dms_agent.py：DMSMaterialStore 保留单层 typed legacy 快照和任务段落；DMSP1Agent 覆盖三工具与材料视图。普通 bank content 仅为确定性索引，原材料不反复嵌套复制。已有组引用展开到材料，legacy 保持独立身份；原文目录／角色及未知关联不丢失。legacy 窗口不仅验证digest，还校验task_id、cycle_id与可取得绑定身份；不匹配即拒绝，不能退回未校验正文。已有活动组之外的历史条目不会自动展示为当前条目。

runner 只新增显式 dms-inspired-v1 候选；源码身份清单包含 62 个实际依赖。SourceLinks 原存储没有新改动；DMS 子类拒绝把其他候选存档静默转换。既有原六例的 source_windows 明确是重建上下文，不是原历史精确生产 manifest。

初始状态不清空、不升级；工具无 status 写入口。保留的错误 legacy 文本可能仍影响选择，宿主不会替模型判错或保证删除正确。仍可能漏选来源、选错组或只读首页；原文结构减少自由断言的机会，不证明消除这些语义错误。

本轮新提示是原文材料选择职责，不叠加旧自由摘要 system。输入仍含完整任务、全部当前活动记录和最近八步动作回执。仅 DMS 强制禁用不兼容的 BM25 预过滤，因为 bank.content 是 ID 索引而非自然语言 payload；不新增检索器。超过阈值的关键词仅在原文组也必须展示，旧候选开关保持原样。保留既有状态截断规则；大 bank 未做规模优化，可能增加输入长度。

本次接口修复采用单一冻结标识解析器，read/delete共享同一映射语义，歧义统一拒绝；E/T/STATUS仍只读。delete执行参数由宿主解析，模型原始调用不变。仅DMS启用tool_error/invalid arguments/cursor/source_not_displayed的fail-stop hook，旧候选默认False。预算限制与部分/未关联来源不是协议错误，保持原有预算及读取语义。没有让模型迁就双ID、没有新增工具或整理判断规则。
