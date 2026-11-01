# P1 历史角色隔离与范围记录窄修

源码已发布：`9e05fe51ee7375f2c4f0a6127aa7519aa463faea`，基于 `25f4adbca08661eda4ae4b607efaedc213f7f711`。最终交付提交由线程回复给出；该提交只增加本目录文档和离线输出。

仅修改独立 SourceReadP1Agent 的提示、P1 输入外层角色标签、读源视图和原始输入归档。保留原始任务、动作、参数、回执和未知混合文本。没有清除旧 [SYSTEM]/[RULES] 文本，也没有开发通用清洗器；明确将其隔离为历史数据。已知工作记忆外层仅标记 observation_content_role，不改内层 {content, tool_results}。旧代码中的同名字面值不删除。原有 project_steps 的工作记忆压缩仍存在，本次没有修改共享算法；投影前完整材料另存归档。

P1 明确维护另一 Agent 的记录，只使用六个记忆工具。配置写入／动作完成不代替预期效果的回执，旧完成记录和 Actor 自述不代替观察。通用范围规则没有题目专用解法。

完整预投影输入保存在 raw_generation_context；实际模型输入另存 model_input，input_projection 记录投影。读源外层始终标明历史数据；预算内按既有顺序保留整条动作／回执及自述，原始预投影副本不直接返回。source_text 是此读源投影视图而非完整归档；旧无来源边界的混合文本仍保留为历史数据。来源窗口不是逐句真值证明。

展示 ID 可用于读源或删除，默认 BASE 的措辞不变。六工具 schema、至多两次读源／一次续答、保存新 ID 再删除旧 ID、未知工具拒绝均不变。续答仍为完整输入加可见调用／回执的文本续接，不是原生 messages 工具续轮。默认路径、共享 P2 提示／输入／解析／投递和冻结六例字节不变。候选未扩接完整 Task launcher。

31 项离线工程检查通过；本轮真实模型、Task、P2、评价调用均为零。假客户端只验证接线，不能证明语义改善。首轮四例结果和失败保留在 [65e6814b 诊断包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/65e6814b306145f81dedd8e70afacf0cdf2e9fa9/pma_evidence_review/diagnostic_packages/PMA_P1_SOURCE_READ_SIX_CASES_FIRST_REAL_20261102.zip)，ZIP SHA-256 `9b0ed2927c6907fad59d684944b325dabc25d6313fadda0cb40952db5e9afbe5`；未声称首轮六例全跑完或读源已有增益。

完整提示见 SYSTEM.txt，逐字变化见 PROMPT.diff；工程差异见 ENGINEERING.diff，哈希见 MANIFEST.json。Windows 后续步骤见 HANDOFF.md，须主线程审阅并另行授权后才运行新批次。
