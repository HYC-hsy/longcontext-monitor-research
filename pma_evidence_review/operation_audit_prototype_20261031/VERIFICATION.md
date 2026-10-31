# 最终检查与证据边界

## 实际完成

- 最终 Python 源码 15 项定向离线契约测试通过，见 final-test-output.txt。
- 独立复核宿主操作分类、冻结删除目标绑定、生产错误状态映射及失败子项解释。
- 生产代码未接入，未调用真实模型，未启动 Task，未执行原生评价。
- 未重跑旧组。固定生产基线为 48babf4302563bbe6e8f0d47e8c617d041a392b1。

## 历史案例与候选投影

来源：
https://github.com/HYC-hsy/longcontext-monitor-research/raw/11fcbd65e11ba66cd1514a5d2e55ccaf4f2bba25/pma_evidence_review/diagnostic_packages/PMA_TAG_SELECTION_SQLITE_FIRST_REAL_TASK_20261031.zip

原包 4,091,226 字节，33 个成员，SHA-256：
d1abddfaf5041d4c8b4f8293ae9f3ffcca06936d19054800c2d5931857b63916。
已核对本地归档字节 SHA 与 ZIP CRC。选取 tag/review/requests.jsonl 与 responses.jsonl
中 call_index=76 的记录，以 JSON 重新排版保存；这是公开脱敏投影，不是原始 HTTP 字节。

历史原操作拟关闭 PATH gap，子项是四个局部事实。旧审核实际给出 overall supported，
不修改也不追认此结果。历史已出现完整操作和 overall，因此本轮不能称为首次补上整体审核。

candidate_path_request.json 由最终 from_closed_material 和 system_for 直接构造，
没有模型响应。3 段 submitted_quote 字符串（含空白）与 4 个原子项逐一保留；来源 role、
field_path、event_order 和同一引文的 alternative_origins 关系保持。
原始 source_id、版本、hash 等保存在 candidate_path_host_mapping.json，不进入模型视图。

同一历史案例的字符数（不是 token 数或计费测量）：
- system：3674 → 2889。
- prompt：2995 → 1994。
- 合计：6669 → 4883。

本轮同时改变提示组织、宿主投影和输出协议，后续不能将变化单独归因于提示文字。
旧响应保留为历史事实；本目录没有把手写理想答案当作真实新响应。

## 可证明与不可证明

离线假响应测试证明协议完整性、必审项合取、缺口反馈和宿主映射按代码工作。
它不能证明 LLM 真正执行四步流程、理由实质充分、不会再误放，也不能证明 Task 得分改善。
生产仍需接入实际 transport、既有引文及版本资格、请求归档和原有 repair/publication 路径。

上游借鉴边界见 REUSE.md。未公开用户原图、凭据、私有端点或隐藏测试正文。
