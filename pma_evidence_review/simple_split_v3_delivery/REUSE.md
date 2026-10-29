# 实际参考和复用

本轮读取了本地固定版本的实际代码，而非仅看项目介绍。无需下载或执行上游依赖。

| 来源 | 固定版本 / 许可 | 本轮处理 |
| --- | --- | --- |
| eea/rag-facts-check | `b78a08213ba7e6d9e587bfa3134ba9047cfaf677` / MIT | 阅读 `rag_facts_check/checker.py` 的 `_to_claim_objects` 和 `_single_batch_verify`；延续“先抽取、整批判断、按原顺序重建结果”的流程。实际执行已有 vendored `VerificationResult` 和 `format_documents`，不新增下载。 |
| aberaio/sourcecheck | `d81493d239ea084c6063695b6e762c2626dd5646` / MIT | 阅读 `src/sourcecheck/types.py` 的结论/弃权定义；沿用本仓库已有不默认正判的原则。未宣称 v3 新增执行其完整框架或检索器。 |
| shmsw25/FActScore | `f28272deffcf33efc1f1117d5479c10bb75221a9` / MIT | 阅读 `factscore/atomic_facts.py` 的句子/原子事实流程；不引入其运行时 NLP 下载、示例检索或 OpenAI 客户端。没有新复制 FActScore 代码。 |

实际复用文件是 `vendor/rag_models.py` 与 `vendor/rag_prompts.py`；已有 `vendor/RAG_LICENSE`、`vendor/SOURCECHECK_LICENSE` 与原 `claim_split_delivery/REUSE.md` 继续保留署名及来源。v3 用 `format_documents` 时预算大于完整已提交 B 的字符总数，避免其默认裁切；格式器的显示序号不进入输出合同，也不要求模型返回 ID。

必要改写：不使用 `Claim` 的 original-text/span 定位，不复制 fuzzy matcher（标点删除可能改变不等号含义），不让上游缺项默认值替代严格结果基数检查，不导入自动检索、静默 claim cap、跳过无引用观点或默认正判。原策略 v2 保留。
