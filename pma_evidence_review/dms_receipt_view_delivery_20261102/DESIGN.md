# 复用、预算与范围

复用既有SourceArchive精确{content,tool_results}识别、call_links身份配对、DMS中央事件表、原文分页与source_identity。旧候选source_view行为不变。新展示只进入DMS已选事件；legacy窗口/任务段落仍按旧预览。没有第三方未许可实现、LLM摘要、检索、证据评分或Planner。

解析只针对已知host envelope和完整JSON对象回执的既有stdout/stderr/status/exit_code等字段，其他键整体保留为未分类原文JSON。配对只采纳既有explicit结果，不按位置/内容猜配。Actor历史独立分区，不能挤掉回执；必要时显式省略。首个receipt字段展示身份，后续用receipt_index关联，空回执保留空结构与可得身份。

每事件完整序列化上限=旧_fields原预览JSON字符数+512，正文总量仍不超旧字段min(800,len)之和；非事件材料不变。优先动作及短流，先缩Actor/metadata/未知剩余块，再缩长流，必要时省略数据行。最多16数据行。元数据独立列出省略行范围、角色数、未显示回执数、未分类字段数和raw入口。不是仅给text计预算；即使1000/5000键或1000空回执，最终JSON仍有界。metadata本身超限则明确工程失败，不发超限预览。

长文本只取原字符串连续片段，真实LF尽量对齐；CRLF/Unicode保持，长单行明确mid_line。<=2048字符的短stdout/stderr优先完整，仍服从总上限，不保证所有短回执在多回执场景都完整。无错误关键词或固定任务/位置特判。

## 测量来源

固定公开ZIP：https://github.com/HYC-hsy/longcontext-monitor-research/raw/51536f4a6014a6da0625b5003ef8b6f4e317201a/pma_evidence_review/diagnostic_packages/PMA_P1_CONTEXT_DMS_NINE_REAL_20261102.zip 。fixture只提取公开B事件及call_links，不复制source_links.secret。

六例测量是最终活动bank、无新增轨迹的下一次maintenance完整序列化输入；before为183e67预览、after为当前renderer，不是原始模型请求。公开旧窗口部分digest与生产记录不同，临时重建目录明确重关联公开字节，逐项记录原/公开hash；不是生产manifest，不放宽正式校验。前后使用同一材料。原事件ID/raw/hash、归档及分页不变。MEASUREMENTS同时列每事件实际JSON长度/硬上限，全部满足。
