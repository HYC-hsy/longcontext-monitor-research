# 独立 DMS-inspired P1 候选

固定源码 `053cff29aa2c03c65c785a3f2f63dae4a4ac5bc9`，基线 `eb406f2a4b1cc74d8d4a34f21fe958d558fa0c4e`；最终文档交付 SHA 见线程回复。分支 pma-p1-dms-20261102，入口 --candidate dms-inspired-v1。没有合并另一条摘要修复线程，没有启动真实模型／Task／P2／原生评价。

P1 仅用 memory_keep(category,source_ids)、memory_delete(memory_id：冻结M别名或已展示真实ID)、memory_read_source(memory_id,cursor?)。类别沿用 knowledge/procedural/gap，但模型不能写正文、标题、成功标记或新 status。GAP 是模型选为待确认的材料，不是工程认定失败。失败和单步经历都可以保存。

正文由宿主从中央来源表确定性呈现。plain-bank content 是程序生成的材料 ID 索引，不是自由摘要；完整原文保存在中央事件／legacy 快照中，由本候选 P1 renderer/read 展开。现有 P2 不能把 bank_after.content 直接当原文消费；后续接 P2 必须另作适配，本轮仍禁用。当前组视图显示原文字段前 800 字符并明确显示 total/preview_only，未显示部分用同一只读工具分页；不冒称看过全部。Actor 自述字段明确标为 self-report，不升级成回执。

TASK 原文保持完整。T 段落按空行确定性偏移切分且保留原空白；E 为完整接受事件，按宿主接受顺序组织，调用 ID 缺失／冲突保持未知。事件表按可靠接受 ID 去重，不同执行同输出不合并。memory_keep 组不承诺按来源集合自动去重，组数量不能当作执行次数。不能事后编造事前意图、precondition 或 goal。

初始 bank 逐字保留为 legacy 派生区，旧 status 仅作为历史派生文本。选择 M 时冻结 typed legacy 引用，中央快照保存一次；新组不嵌套复制旧文本。删除旧活动条目后，已引用组仍能回查摘要及其原生成窗口；无窗口明确 unrecorded，旧窗口只是宽范围上下文。含 legacy 未关联材料的组，即使页序读完也 complete=false。A+B 可以同时保留，不另写只绑定 B 的综合状态。

三工具沿用最多四次读源／三次逻辑 P1 调用，最后轮只 keep/delete。每页整体 JSON ≤8000 Unicode 字符，超长材料可连续拼回。来源不是证明，继承不是已读，部分不是完整。保存失败、禁止或未知工具阻止同批后续操作；此前已经逐操作提交的有效 keep 保留，不是整批事务或全批回滚。提交前后异常通过既有单一持久包对账，不新增版本图／审核／回退。

当前73/73离线检查包含旧58项回归与15项DMS检查。旧66/69报告及此前六例scripted CLI保留为历史，本轮没有另起案例批次。假客户端不是语义改善证据；原六例文件、初始 bank 和观察维度不改。Windows 真实 P1 新六例指令见 HANDOFF，须主线程审阅固定材料后交付执行；Mac 不加载私有 profile。

旧 source-read / source-links-v1 的实际提示、schema、预算和合法协议保持原样；新增两个类属性仅使新候选可替换 system 和失败写名称，末轮文字也有保持原值的 hook。共享源码身份字节改变后需重新生成旧候选 manifest，不能跨 checkout 复用证书。

详见 DESIGN_REUSE.md、TEST_RESULTS.md、SYSTEM.txt、TOOL_SCHEMA.json 和 MANIFEST.json。公开内容仅源码、测试和脱敏离线投影，不含完整 profile、凭据、私有端点、隐藏推理、signature 或 source_links.json 内 cursor secret。

删除接缝已在工程修复：read/delete共用冻结标识解析，M别名和已展示真实ID对准同一记录；歧义、碰撞、已删或绑定变化直接拒绝，不猜ID。E/T/STATUS可读不代表可删。模型原始参数不改，receipt/operation另记requested_memory_id与resolved_memory_id。失败删除、无效工具参数／cursor等协议错误后停止同批后续操作，已逐操作提交内容保留。source_unassociated/partial及预算限制不当成语义失败。DMS真实实验尚未启动；A归档992f7b56仅为接口问题背景，不是本路模型结果。
