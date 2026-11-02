# 给 B 的复用边界

最新固定源码 `26ff924d083616c5b6c91136b6ee6af312f8f83c`，95 项检查通过；不要复制正在修改的工作区。相对 f6a3982b 的同步内容见 SHARED_HISTORY_PATCH.diff 与 A_BINDING_HOOK.diff；helper 的 record/coverage/read/load 接口未改。

diff 为零上下文对照；固定干净 f6 副本可用 `git apply --check --unidiff-zero` 预检。B 应按自己的保存路径适配，不盲目覆盖已修改的 agent 或导入 A 提示。

核心文件在 `method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/`：

- p1_context_history.py：小型 helper，仅标准库及已有 encode/digest；最新补丁独立处理 sources 可用性和明确引用目录。
- p1_source_archive.py：capture 的可选 input_memory_coverage 字段；旧调用默认不写该字段。
- p1_source_links.py：既有分页器的可选目录、元数据、原子条目及排序参数；旧调用默认行为不变。
- p1_linked_agent.py：可覆写的 _capture_window hook；默认仍调用原 capture。
- p1_linked_agent.py：新增默认等价的 _resolve_sources hook；A 在 resolved 元数据加入已验证的 cited_history_handles，仍交给同一次 bind/commit。B 不必导入 A agent；在自己的保存路径验证 H grant 后，将该列表与 sources 一起提交，不能另起第二次写入或改冻结 window。

B 不需要导入 A 的 p1_context_agent.py、SYSTEM 或 GAP 定义；该文件只供接线参考。这里没有合并 B 未完成代码，也没有为不同 bank 设计通用版本图。B 仍需针对自己的 typed legacy ref 做明确适配并验收，不能仅复制文件就宣称接通。

## 接口

`InputMemoryHistory(links, archive)` 使用既有 task-scoped SourceLinks 状态/事件表/commit/read 与 SourceArchive 的 task、task_id、window_path。

- `record(memory_id, category, content, ref)`：冻结已展示记录；ref 为已有 SourceLinks 绑定格式，未知时用 None，不能从文字猜 ref。
- `coverage(records, presented_receipts)`：形成 window 可选覆盖字段。宿主负责选取实际展示内容；不传完整隐藏 bank。续轮保留初始展示快照，不能换成更新后的当前条目。
- `read(target, active, requested_view=None, cursor=None, handle=None)`：普通目标须来自本请求已展示对象；历史目标用实际返回的 H1 handle。校验/完整性错误可抛 HistoryError，宿主须保留其 status，不能改成宽松回退。
- `load(handle)`：只接受已授予且校验通过的 handle，返回不可变内容/类别/ref 快照。B 可据此接入 source_ids，不能让“可读却无法合法引用”的协议接缝重现。

窗口保存记录内容和冻结 ref；小型 history_grants 地址表保存在原 SourceLinks 状态中，只有实际返回的完整目录条目才获准。没有另造证据库或复制祖先原文。H1 不进入活动 bank，不可删；与显示别名/真实 ID 冲突时宿主必须拒绝。

A 的 source_ids 接法只临时扩展本次解析映射，不改写模型原始调用；历史 ref 按已有继承规则展开，未知继承继续保留。读取、引用、删除权限与原始参数日志都应由 B 自己测试。既有读预算和最终 write-only 约束仍归宿主维护。

明确引用 H 的身份也要保真：cited_history_handles 是输出 ref 元数据，不是生成前 input coverage。目录内先列 explicitly_cited_history，再列 displayed_record/earlier_read_handle，并保持 original_read_not_implied。合法旧 H 可直接复用已有 grant；不重新发明历史地址或强迫模型先读原文才允许引用。

sources 模式中，输入窗口/目录失败只让辅助覆盖变 unavailable/integrity_error，不遮蔽独立完好的所选原文；不授予坏 handle。明确且有效的输出引用可独立保留。context 与自动回退 context 仍严格校验。首次新 handle 授予会持久化元数据，任何写失败必须保留工程错误；只读不表示没有 I/O。

目录项独立标记为 input_memory，长目录原子分页；历史派生内容标记为 derived_memory_content，原始来源和生成输入保持原字段。所有成功分页 JSON 的元数据均进入 8000 字预算。完整页序只是传输完整，不是语义证明。

预算是最多四次总读，但仅 r0/r1 可串行发现新 handle/cursor 并跟进，r2 只写；sources 目录在大来源之后可能本轮尚不可达。helper 循环百页是传输检查，不能据此宣称 P1 能一轮读完任意历史。
