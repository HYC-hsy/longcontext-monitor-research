# DMS已存材料的回执展示修复（仅离线）

源码固定 `3b34b6a813364b935862a9998febd6d20e321b48`，基线 `183e67ae70592bb0f5b7d16e3db53750a4ff4b1c`。独立分支 pma-dms-receipt-view-20261102，最终交付SHA见线程回复。仅改存后重建展示，未改保留/删除策略、摘要准则、SYSTEM、工具schema、读源分页或4读/3逻辑调用预算，未合并其他线程改动。

真实B九例包中，P1当轮初始输入确实含完整回执。本缺陷发生在材料保存后的组预览：旧展示将整个observation前800字符暴露，历史WORKING MEMORY挤掉后面的实际tool_results。不能据此说模型当轮从未看到失败。

现在按已知{content,tool_results} envelope分开动作/参数、可见工具回执、Actor历史/自述。对已知JSON回执保留status、exit_code、stdout、stderr等原值，其他字段保留为未分类数据；外壳success、exit_code=0都不代表任务成功。未知格式不猜字段，仍有原文预览。配对只复用既有真实callID及歧义结果，不按位置或文字相似猜配。

长字段采用确定性头/尾区间，头约1/4、尾约3/4，明确总长度与省略范围；短字段全文。每个选中事件的原文字符总预算不超过原_fields各字段min(800,len)之和，Actor只先预留有限份额，不能抢占回执。重复身份元数据只在对应receipt首次出现展示；后续字段通过receipt_index关联。完整raw archive及原文分页完全不变，展示是projection而非原始HTTP字节。

B01 event_7、B04 event_8的配对动作与command not found/Segmentation fault原文在新预览可见（算法无这些词或语言/任务特判）。这只是fixture预期通过，不是语义效果评分。头尾展示仍可能省略中间信息，读源预算不保证一轮读完；新结构也不保证模型更改删除或旧结论选择。

当前77/77离线检查通过，包含旧73项与4项新增展示回归。真实模型/Task/P2/eval调用均为0，未启动或重跑真实案例。本轮没有改变P2，未来消费新projection仍需明确适配，不能直接把bank_after索引当原文。

原SYSTEM与schema完整文件继续在同提交dms_p1_delivery_20261102目录，SHA见IDENTITIES。旧候选共享的SourceArchive仅抽出同一识别条件的纯函数，source_view输出结构/内容保持原行为；没有导入未许可第三方代码。

详见DESIGN.md、TEST_RESULTS.md、MEASUREMENTS.json、MANIFEST.json；HANDOFF仅离线验收。本目录公开输出均无profile、凭据、私有端点、hidden thinking/signature或cursor secret。
