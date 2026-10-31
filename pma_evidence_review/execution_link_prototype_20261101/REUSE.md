# 复用边界

固定生产 a0f35e1ab4586472ebc0768b87e3cc228f36aa14，实际检查：
pma_evidence_review/operation_audit.py、claim_split_semantic.py、live_citations.py、inputs.py；
D/gap_evidence.py、evidence_gap_context.py、citation_gate_agent.py、episode.py、evidence_gap_store.py；
operation_audit_delivery/frozen_replay_cases.json、historical_path_material.json、replay_three.py；
根AGENTS.md。D路径见HANDOFF。

实际接口复用：SourceRecord、SourceSnapshot、parent_wrapper、已存在的 _validate_catalog 回调，
命令id/结果tool_use_id的原注册映射。原型未复制作者运行类，生产只需接这些原接口。
context_from_catalog 的 accepted-public-envelope hash公式按已读 event_identity 的确切字段/
ensure_ascii=False/sort_keys/compact separators重现；不是raw HTTP hash。

未声称当前catalog本身证明完整调用一一对应：仍核完整accepted event ID inventory；源text
不因host witness可见就成为新B。使用的是项目已有消息关联实现，不移植外部工具框架。
前轮SJC/SAM的共享材料/原文边界仍是说明性借鉴，本轮未新增任何作者实现复用或检索。
新函数和测试均标准库，未引入协议库、第三方代码/依赖、额外模型角色或语义成功判断。
