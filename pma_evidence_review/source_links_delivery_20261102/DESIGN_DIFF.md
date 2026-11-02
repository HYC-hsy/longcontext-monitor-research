# 设计落实与边界

设计依据：[固定 DESIGN](https://github.com/HYC-hsy/longcontext-monitor-research/blob/ef2b33edd6e4ab3ff4a91ad9820e0a33e2df742d/pma_evidence_review/source_link_design_20261102/DESIGN.md)。设计提交不是源码基线。

|设计项|实现|
|---|---|
|集中事件与调用配对|p1_source_links.visible_event/call_links/SourceLinks.ingest；表中保存一次，审计输入仍独立保留；无 ID 的呈现分开保存|
|三类摘要和状态来源|LinkedSourceP1Agent._input/_apply；source_ids 可空；M/STATUS 冻结后展开；未知继承不被后续有效来源洗掉|
|同一读工具分页|SourceLinks.read；原字符串区间或结构化值的 JSON 编码；目录也是可分页字段；HMAC cursor 绑定任务、目标、来源快照及位置，不能指定路径|
|来源变化|首次读也检查请求冻结 ref；同批 status 更新后旧 STATUS 返回 source_changed，等下次维护重新展示；不自动加一轮刷新|
|原子性|同一文件的当前 bank 与 refs 一起 replace；异常前后注入测试验证无幽灵绑定；对账已提交的保存仍记 success=true，并另记工程异常及 persistence_outcome|
|完整性|完整页序与来源完整分开；有未知继承或无关联不能报完整；删除只去活动条目与绑定|

最小选择：只支持完整 TASK（没有新增段落切分）；保留旧 memory_id 读参数名，增加 cursor；状态入口用 STATUS。显示 bank 的 BM25 开关、原阈值与每类 top20 规则、status 长度截断保持原设置，绑定保存实际截断后的 status。持久化重开要求传入单一提交包中的当前 bank；不迁移旧 evidence/revision 格式，旧入口仍按旧类读取。

新增两个运行文件 p1_source_links.py、p1_linked_agent.py。既有 runner 增加显式候选选择并把两者加入实际启动 source_identity；默认候选的语义不变，但新的 checkout 须重新生成源码身份，不能复用旧 manifest。无 frontend/Task launcher 接线。

参考复用：按用户批准设计借鉴 MAGE 的事件／摘要覆盖分离、SAM 的目录与原文续段思想。本轮实现全部自主编写，没有复制 MAGE 或 SAM 代码；MAGE 核心许可未确认，未移植；SAM 固定 ac23445 的 MIT、PageStore、page_memory 仅为设计参考，没有再摘要、reasoning serializer、split/join 空白变更、淘汰原页或额外 LLM。未新增供应商运行依赖。

限制：只处理允许可见输入；未知 payload 保守保留为历史数据，不做通用隐私清洗。单任务单 writer 串行维护；未实现并发写入合并、完整 Task 生命周期或 P2 读源。页数可超过本轮预算，目录/包可寻址不保证一轮能读完，也不保证模型选择来源正确。
