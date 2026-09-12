# R2适配完成：固定轻量态势，按需取证

## 审计结论

机制提供不等于能有效使用。R1让模型自己决定何时组装判断输入，又给了一个包含大段重复原题、记忆和工具参数的工具；后者不能稳定替代日志查询。PMA的固定上下文与LivePlan的recent窗口应借鉴的是输入组织和消费关系，不是要求多调用某个工具。

本次不是模型训练或自动学得策略；是依据真实轨迹修改harness的使用机制。研究问题、单一监察者、同会话、两层、无checker与任务并发保留。

## 实现

- `decision_context.py`：新增attention读取既有synopsis最后4条（最多读取文件尾64KiB），每条最多1000字符预览，附上最近提交纠偏最多1500字符。无模型、无语义分类、无醒来触发、无读取即采纳标记；任务可在模型推理期间继续前进。它不是逐token监视。
- `agent.py`：通过既有prepare_active_context路径临时提供attention，请求完成即移除，不重复堆入History；仍由原active-working开关提供私人工作认识。模型可自由继续调查、立即纠偏、选择暂停或静默；不强制写记忆、不强制调用review_context。稳定提示只解释这种分工，不加Fyne领域规则。
- `review_context`：仍复用原PMA BM25及LivePlan renderer，作者文件无改动。query现在同时检索题干与私人笔记，working不再作为笔记重复命中。正文、工作认识、指导、动作与结果各作标注裁剪，来源仍可按通用工具打开。默认after_correction=true，但可显式false回看纠偏前。所有快照仍不是完成证据；工具裁剪可能丢关键信息，原始取证能力未裁剪。
- `provider.py`：仅工具型最终输出之前的纯空白delta不作为正文冲突，工具身份/参数校验照常。非空白delta冲突、缺最终完成、工具参数矛盾仍拒绝；增加短delta的Unicode码点诊断。R1字符未知，因此不能宣称修复了R1所有重试原因。
- 暂停运行时、租约、任务中断、根完成控制不改；零使用不能据此判死刑，也不强制激活它。

## 验证

- 297项监察/中断回归通过；64项隔离/入口回归通过。
- 新增检查：临时态势不积累、变化可见、跨任务隔离沿用回归、默认纠偏后/显式回看、巨大动作预览且原文未删除、题干末尾查询命中、working不重复、工具前空白不入会话且矛盾工具仍拒绝。
- 同一R1窗口输入回放：47360→14256、109072→15684、112300→17533、143191→18611字符。事件来源一致；query优先原题摘录。为了只比较表示，回放显式关闭新after_correction默认，并从旧工具结果重建当时笔记；不能据此评价新默认或真实模型效果。详见artifacts/literature_transfer_20260913/r2_view_comparison.json和compare_r2_views.py。
- 新manifest：`artifacts/literature_transfer_20260913/fyne_r2_manifest.json`；同Fyne、Opus4.8/sol high、500轮10000秒、断网Unix推理；未启动、零API。runner preflight另行核对源码/镜像。R1/旧manifest不复用。

Git回退tag `pre-literature-adaptation-r2-20260913`；设计a614a73，输入适配0f820e6（156增32删），协议7623338（39增1删）。本轮没有提交既有.gitignore改动。回放脚本及派生数据独立保存，不计为方法效果。

## 未解决与下一轮判别

always仅用于有限态势，不是固定全部证据。还有三个未证问题：压缩预览是否导致漏看；固定新鲜视图能否抑制调查惯性而不打扰深入判断；有限暂停是否有自然使用场景。不能据输出变短宣布成本/质量改进。未增加强制行为、分类器、小模型或另一套记忆层。下一真实启动需用户单独确认，只运行这一条R2，不自动追加对照。

来源：本地PMA author commit89e5c0d6、LivePlan author commitc16797a，与上轮NOTICE一致；人工Fyne011/014原始输入及R1真实dialogue/工具结果已对照。协议按[OpenAI流式事件文档](https://developers.openai.com/api/docs/guides/streaming-responses)区分事件与最终输出；纯空白容错是本地适配，不是官方保证中转会产生空白。
