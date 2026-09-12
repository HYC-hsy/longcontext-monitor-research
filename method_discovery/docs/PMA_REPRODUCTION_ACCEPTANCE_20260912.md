# PMA 保真修补与两类比较的验收

## 本阶段裁决

当前名称仍为 **PMA-sync GA adaptation**。直接复用官方三份核心模块，不等于已复现原论文效果。本轮只修补确定的信息/注入接线差异，不切换模型、不增加任务、不调用 API。

固定参考：`https://github.com/yifannnwu/proactive-memory-agent`，commit `89e5c0d6aadfe531a1aee42fd290d48be89973dd`。

## 已修复的两个差异

1. 旧 `agent_loop.py` 只将 tool_results 提供给 PMA，遗漏任务实际收到的 next_prompt，包括 turn_end_callback 产生的公开反馈。现在将最终 next_prompt 与 tool_results 一并序列化为该步 observation。既不引入隐藏 checker，也不新增语义摘要；原八步格式与原 PMA 提示不变。
2. 旧接线追加独立 user 消息；现在按发布 YAML 的 `injection_method: user_turn` 将提醒追加到当前 user 内容，保留工具结果 envelope。字符串输入与已有多模态块均不丢弃；无提醒时不改消息。

验证覆盖实际 GA 循环而不只测 formatter：两个 phase 均收到 sentinel 和 callback 反馈；初始消息仍是 system+user，普通下一轮仍一条 user；tool_results 内容和 ID 保留。另直接抽取官方 `_get_memory_system_prompt` 比较提醒文本及单次消费。三份核心源码仍逐项一致。

## 官方依赖核对纠正

应以该仓库 `external/harbor` 为参考，不以其他项目缓存的 Harbor 为替代。本次核对作者 `external/harbor/src/harbor/llms/lite_llm.py:274`：显式接收 system/tools，默认 message_history 为空，将 system 与当前 prompt 拼装后调用；这支持两个 phase 独立输入、更新后的 bank 进入 phase2 的适配。标题注释中的 shared conversation 不能替代执行代码。

该结论仅限调用语义。作者使用 LiteLLM、Anthropic caching、自己的重试/参数处理；当前桥接使用独立 MonitorProviderClient。因此不能宣称缓存、重试、输出上限、采样与成本完全等价。当前 Responses 分支没有发送 temperature；不得把配置里写 temperature 当成实际生效。模型更换及参数协议需单独批准，不在本轮擅改。

## 轨道一：官方原配置复现检查（尚未执行）

- 使用作者完整 memory_enabled_agent、runner、vendored Harbor，而不是 GA 接线。
- 以发布的 `configs/memory_terminalbench.yaml` 与 baseline YAML 为可执行参照：Terminus2，Sonnet 4.5 task / Opus 4.6 memory，temperature 0.7/0.3，max_turns 50，XML parser，enable_summarize，8步窗口、逐步触发、user_turn；实际参数需核对 runner 最终请求，不能只看 YAML。
- TB2.0 发布配置列89题，但增加/切换题源、运行规模、原模型可用性与预算均需用户批准；不能据本文件启动。
- 原作者允许从 Enroot 改 Docker，但应显式记录环境差异。现行无网络防泄露边界不能静默取消；若与原题网络需求冲突，先决定研究者可接受的复现范围，不能把失败算方法问题。
- 小规模 smoke 只能证明原版能跑及行为合理。声称“复现论文成绩”还需核对论文实验设置、任务版本、重复次数和聚合口径，再得到相应完整效果证据。没有这一步不得在结果表里写 reproduced score。

## 轨道二：共同 GA 底座机制比较（当前代码服务于此，效果未验收）

- G0/G1/PMA/候选统一任务 Agent、任务版本、初始化材料、隔离、资源政策和离线评价；PMA 与本方法尽可能用同一监察模型，以控制模型能力差异。
- PMA保留官方记忆机制及同步逐步触发，不加入我们的主动工具、连续会话、强制中断或完成控制。我们的并发是待实验检验的差异，不以改成异步的 PMA 冒充原始实现。
- GA公开response映射analysis、无独立plan、GA工具结构/完成/压缩/解析逻辑不同，均作为适配差异披露。不为复现Terminus2而暗中改所有GA条件的结束行为。
- 同时记 task/monitor 调用、输入输出/缓存token、延迟、wall time、可得费用与异常。相同时间上限可能使同步基线少完成工作；要单列调度成本，并按论文声明设计质量与资源比较，不能把这种影响隐去。
- 发布模型/温度/预算并非当前共同底座协议；尚需冻结最终请求参数和超时策略。任何参数不支持都必须披露，不能宣称等参数。
- 下一验收应是单次干净真实运行、完整归档与对照，而不是继续无限增加静态格式测试。启动前仍须确认 task/model/budget/expected cost。

## 工程验收与未闭合项

本阶段22项测试通过、另3个源码子项通过（PMA、上游一致性、Clean runtime）。未启动模型；原三核心与Clean机制未改。修改为agent_loop接线、PMA提醒助手/NOTICE、两份测试与文档。单步代码增删低于600行。

现在能称：官方核心代码直接复用，并修复已确认的GA观察/注入缺口。仍不能称：完整原配置复现成功、原论文效果已复现、GA适配效果与原版等价。两条轨道均未获真实效果验收。
