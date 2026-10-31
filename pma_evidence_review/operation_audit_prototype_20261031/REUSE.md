# 真实复用和仅借鉴边界

实际检查的固定代码：
- HYC-hsy/longcontext-monitor-research @48babf4302563bbe6e8f0d47e8c617d041a392b1：
  AGENTS.md，pma_evidence_review/claim_split_semantic.py、claim_split_simple.py、
  claim_split.py、live_citations.py、citation_inputs.py、operation_review.py、
  gate_control.py、REUSE.md。旧 overall 合取与返工已经存在，不据此制造新贡献。
- GuanghuiMin/sjc @771517bebf49b9d45aa7bd48c7f5daec883c6282：
  sjc/gate.py 的 request/prune 和 sjc/jev.py 的 Jev.ask 实际读取。
  request 一份 state 关联多个 questions、ask 按宿主 questions 聚合，作为共享证据
  批处理/宿主关联的设计借鉴。gate.QUESTION 只问包含环境来源的信息，并不证明整个
  结论成立；prune 失败保留 raw summary（fail-open），本轮不照搬。没有复制其模型、
  阈值、token 上限、重试、网络客户端或 summary policy。
- qhjqhj00/cabeza @ac23445a44b6c2eee586ab32f52c8cf98df8f8bf：
  src/cabeza/prompts/_defaults.py 实际读取：不确定时确认、关键结论 open_page
  查看全文和 confidence 要求仅提供说明。未读取其全部 memory 实现，未声称复用
  原文回查实现；本轮不接入 search/open_page 或其它回查工具。

本目录新写标准库契约，没有复制以上作者实现函数，也未 vendor 许可证代码。
因此不声称“采用 SJC/SAM 实现”。生产开发应实际复用现存 v3/v4 的调用、引文
校验、聚合、返工和证书基础设施，只作 HANDOFF 列明的适配；本目录是接口原型。
SJC 的来源判断与本轮完整操作证据成立判断不同，SAM 的回查也没有在本轮实现。

## 父环境补充核对：已有审核流程

- [RAG Facts Check evidence-first 提示](https://github.com/eea/rag-facts-check/blob/b78a08213ba7e6d9e587bfa3134ba9047cfaf677/prompts/claim-verification-evidence-first-system.txt)：固定源码已直接读取。其步骤为读取/摘引证据、比较主张、三态裁决、输出。这里借鉴证据优先再比较的专业审核流程；本项目证据已经由宿主提供，因此不重复要求模型摘引、复制全文、生成 document_index 或受它的最多三段限制。完整操作关闭条件和缺口反馈是本项目适配，不宣称上游已解决本次错误。

这些原则性的借鉴与实际复制代码不同。当前原型是新写标准库接口，生产已有 RAG 格式器/容器等许可继续按原仓库保留。本轮未新复制上游实现代码，也未安装插件。
