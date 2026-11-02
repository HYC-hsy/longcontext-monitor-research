# 实际复用与范围

- p1_source_archive.split_visible_observation 抽取已有source_view的精确识别条件：只接受恰好content/tool_results、content为str、tool_results为list的host envelope。source_view也使用该函数，保留旧行为。
- p1_dms_view 是新增纯展示函数，读取中央事件与已有call_links；只在DMS已选来源属于事件表时使用。legacy生成窗口、任务段落保留原预览分配，不递归解析历史对话或猜框架语义。
- content字符串仅当完整JSON对象且有已知回执字段时拆字段，原字符串/值保持原值，不能把未知文本regex猜成新字段。Actor analysis/plan和envelope.content标为自述/历史；未知observation是未分类数据。
- 配额先给动作（最多800），预留Actor最多200及事件metadata最多100，其余优先回执，短字段不用完的份额再给Actor/metadata。公平分配不按词义或错误关键词加权。原始字符预算未增加；JSON分区/范围元数据带来下表精确输入增量。
- 所有保留字段显示全文或原字符串头尾连续范围，省略区间明确，0配额也保留被省略的说明。不会让完整Actor历史把实际回执挤掉；并不声称所有错误一定出现在头尾。
- _fields、read分页、cursor、事件表及source绑定不改，keep/delete路由不改；新增一个runtime文件纳入实际P1 source_identity（63项）。未加入检索、LLM摘要、Planner、Verifier、coverage/证据评分或utility。

## 六例测量方法

固定公开ZIP：https://github.com/HYC-hsy/longcontext-monitor-research/raw/51536f4a6014a6da0625b5003ef8b6f4e317201a/pma_evidence_review/diagnostic_packages/PMA_P1_CONTEXT_DMS_NINE_REAL_20261102.zip 。ZIP hash和事件成员映射见tests/fixtures/dms_receipts/INDEX.json。只取公开B事件作为fixture；不复制source_links.secret或未知私有字段。

测量是公开投影重建的下一次maintenance视图：使用每例最终活动bank、无新增轨迹；不是原始模型请求字节/长度。before用旧_fields前800预览，after用新renderer，其余任务、bank、窗口内容相同。公开包部分旧window文件与记录生产digest不同，临时重建目录明确将公开字节重新关联并在MEASUREMENTS逐项列原/公开hash；不冒称原生产manifest，不修改正式完整性检查。前后对照用同一重建材料，生产事件ID/raw/hash及源包不变。

这不测P1是否保留了早期经验，也不测是否删除旧错误；这两项策略仍由主线程独立研究。
