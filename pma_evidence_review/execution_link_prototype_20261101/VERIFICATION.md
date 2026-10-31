# 验证与边界

最终 8 项定向离线测试通过，见 final-test-output.txt。没有真实模型调用、Task 或原生评价。
独立源码复查确认保留完整 field_path，按 accepted_public_envelope 摘要语义配对。
已确认不同调用保留不同X；缺失/重复/歧义不被强行配对，不自动作为语义拒绝。

## 真实公开材料重建

事件21/23来源于固定归档11fcbd65e11ba66cd1514a5d2e55ccaf4f2bba25的公开脱敏包：
PMA_TAG_SELECTION_SQLITE_FIRST_REAL_TASK_20261031.zip，SHA-256：
d1abddfaf5041d4c8b4f8293ae9f3ffcca06936d19054800c2d5931857b63916。
使用a0f35e1固定event_identity/_project_tool_text/register_public_source重建，12条来源记录
除公开身份字符串空白格式重编码外与归档一致。原记录、事件、重建记录、原文hash和
转换说明均保留于fixtures/event21_reconstructed_sources.json与event23_reconstructed_sources.json。
这不是原始HTTP字节，也不是完整历史visibility manifest。

最终以真实SourceSnapshot/parent-wrapper构建新的离线局部catalog，并执行原
_validate_catalog函数体及其真实gap_evidence依赖。完整gap_evidence_alignment模块导入
因环境缺少regex依赖未完成；没有安装依赖、没有用mock代替该验证函数，也不冒充完整
生产接入测试。函数体来自固定源码，hash与执行说明在reconstruction-check.txt。
新的离线visibility_ref明确是本次重建检查，不冒充历史运行的可见性证明。

核对结果：
- 原B0三条引文及角色/字段/顺序保持，E1/E3为X1的命令回执；E2为另一次X2的单侧输出。
- 原B0仍不含sqlite3 --version命令，没有从宿主完整脚本偷补进模型输入。
- 可选B1只把E3连续span从[35,117)扩至[35,135)，source原文确实存在；不是默认调用材料。
- 三条候选请求离线冻结，未发送。两个正例除追加原计划及对应子项外，事实句、类别、B、
  证据顺序和system相同。人工参考标签单独保存，不在模型输入。
- 第三条为明确人工构造的非SQLite任务：重排后命令与输出同索引但不同调用，投影明确为
  X1命令/X2输出。未选alpha失败只在host witness，不在B，不能用来把参考改为contradicted。

旧B0 evidence SHA：6dfa9de1c6f0ca799b688fdb580d13540cb8f24b39349d3cfb1735347f09a673。
可选B1 evidence SHA：3c8650e47ebe4515eb1d3b4aede148a0855ea97bb18dd5d6e0cdd2bb369cf1da。
版本hash使用既有compact/sort_keys/ensure_ascii=False JSON身份公式。

## 不能据此宣称

未完成真实模型语义验证、跨任务泛化验证或Task收益验证。没有题目专用分支不等于没有
过拟合风险。已见PATH是开发回归案例，不是独立留出集。完整生产接入还须采集真实窗口
inventory、沿原引文资格及版本/提交控制、核对实际请求与返工；不能用本地构造的Context
自授生产资格。旧组不重跑，旧结果/标签不改，不自动启动完整Task。
