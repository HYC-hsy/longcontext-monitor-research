# 复用与必要适配

官方论文：https://proceedings.mlr.press/v306/mi26b.html 。2026-11-02 官方匿名入口 https://anonymous.4open.science/r/DMS-C48C 返回 HTTP 401，代码不可取得；不声称仍是旧的 410。第三方 ychnSu/Darwinian-Memory-System-DMS 固定 e1e995f2d2623b5e0d16268c30beb3c80e900618 的完整文件树未见 LICENSE/COPYING/NOTICE，README 自称算法级复现，Agent 在 dms/androidworld_agent.py。本轮未复制第三方代码、未执行仓库外软件。

DMS 有事前 plan 的 precondition/goal、轨迹及结果元数据。我们没有事前 Planner；这是历史原文分组适配，不是完整 DMS 复现。未加入 utility、风险门控、淘汰、embedding、Actor、Verifier、回放或额外 LLM。允许失败／单步材料，不采用成功轨迹过滤。

复用本仓库 SourceLinks 的事件 ID、实际调用配对、来源排序、字段分页、游标、原子持久化；SourceArchive 保存实际请求／回执窗口；复用 LinkedSourceP1Agent 的最多三轮工具续答、_calls、日志、usage 和预算。只是文本忠实续接，不冒称原生 messages 工具续轮。

新增 p1_dms_agent.py：DMSMaterialStore 保留单层 typed legacy 快照和任务段落；DMSP1Agent 覆盖三工具与材料视图。普通 bank content 仅为确定性索引，原材料不反复嵌套复制。已有组引用展开到材料，legacy 保持独立身份；原文目录／角色及未知关联不丢失。已有活动组之外的历史条目不会自动展示为当前条目。

runner 只新增显式 dms-inspired-v1 候选；源码身份清单包含 62 个实际依赖。SourceLinks 原存储没有新改动；DMS 子类拒绝把其他候选存档静默转换。既有原六例的 source_windows 明确是重建上下文，不是原历史精确生产 manifest。

初始状态不清空、不升级；工具无 status 写入口。保留的错误 legacy 文本可能仍影响选择，宿主不会替模型判错或保证删除正确。仍可能漏选来源、选错组或只读首页；原文结构减少自由断言的机会，不证明消除这些语义错误。

本轮新提示是原文材料选择职责，不叠加旧自由摘要 system。输入仍含完整任务、当前按原配置可见的 bank、最近八步动作回执；保留原 BM25 开关/阈值及状态截断配置。大量新组时 plain-bank 索引的 BM25 匹配质量未验证；本轮只验原六例，不据此宣称长任务检索性能。
