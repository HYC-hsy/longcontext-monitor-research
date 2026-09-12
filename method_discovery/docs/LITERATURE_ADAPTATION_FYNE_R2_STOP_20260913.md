# R2真实运行：适配观察与协议异常停止

## 授权与运行身份

用户睡前批准自动启动、按结果/异常停止，不自动改动重跑。使用`artifacts/literature_transfer_20260913/fyne_r2_manifest.json`，版本b3a6fd5，源码hash6e477502de8b6113927f11e1c26bf6886eb3d836cd74ca5e51f8555aa8cb0773；预检通过。Fyne2.2 / Opus4.8 / GPT-5.6-sol high，500轮10000秒，active-working+decision-context+hybrid-control，旧候选/PMA关闭，no-network-unix-inference-v1。

运行ID：clean-monitor-fyn-2.2.0-roadmap-literature-adaptation-20260913-r2。
trial：fyn-2.2.0-roadmap__KntCVxo。
约北京时间03:08至03:28:41（UTC2026-09-12 19:08至19:28:41），约21分钟；最后task158/cursor312。未到完整终局，native score=null。不得将Agent自述完成当实际成功。

## 实际观察

- decision_attention归档31次，固定轻量第一层确实接入正常推理。
- review_context=0，task_control=0；新详细检索和暂停没有获得真实行为验收。不会强迫使用以制造阳性。
- 监察35次file_read、27次code_run、1次file_write、4次wait、4次intervene。真实读取了代码/测试/原始轨迹，并对照题干纠偏，没有由人工额外注入答案。
- 第一次纠偏指出绑定缺Set与类型处理、菜单Refresh空壳；第二次具体跟进Bytes/URI/identity/partial scan。task41明确响应监察建议，随后实施并测试。task64又称不存在Bytes类型而删除处理，未得到及时单点纠正；这并不表示必须强行中断，但保留为未闭合需求观察锚点。
- 后半段持续读取范围很大的raw事件（例如count240、200），模型请求出现约104/126秒的成功延迟及重试；固定小速览没有阻止它自行大范围取证。不能把“每次提供当前态势”当成已解决时效问题。
- 临近task149自述全部完成时，监察集中指出菜单no-op、Toolbar返回类型/SetIcon、Container、Hyperlink回调、desktop接口等多项不符。随后任务继续修复；最后task158在读Hyperlink回调调用路径。临停止前又一次纠偏仍主要重复同批根要求。
- 上述部分提醒后有行为响应，但无同配置对照、无最终评分，不能认定R2有效/退化或已学会更及时干预。提示/工具的存在与模型如何使用仍需区分。

## 工程结果与停止原因

明确修复生效：27个工具型响应之前出现单个空格（Unicode32），ignored_tool_only_whitespace=true，模型工具调用正常保留；未重演R1的单字符文本冲突重试路径。R1原字符未存，不能倒推它必然同因。

新异常：runtime_receipts记录两次ProviderError，均为`tool result has no matching call_id: call_8VyJL5kfYyr2ayaNiMZaG43Y`，发生在普通审议而非completion=true。随后恢复有成功调用，但同ID反复出现，决定停止，不以更多预算继续碰运气。

该ID是初始化file_read(task/original_task.txt,start1,count1000)。已查三份本地payload裁剪前history归档（bce9c23677a546e1bb89c4ebabed7607、6756d8fb70b94b6499458826fd68aaba、1efa967d3fb64b2d91f0f0178ecc4d14）：均有index1 assistant/tool_use与index2 user/tool_result配对。**这反驳了“本地归档里调用条目已丢失”的直接猜测，但不能证明每次实际线上请求也完整、唯一且被服务正确解读。**下一应检查实际Responses序列、重打包ID/重复调用以及中转处理，不能未经证据指责压缩或中转。此轮未修改协议。

## 用量

监察已返回可见usage28条：输入2,673,475、输出7,301 tokens。没有完整计量无usage或失败请求，不能按此宣称真实账单降幅。任务156条usage：未缓存输入222,991、cache creation285,520、cache read2,907,860（输入合计3,416,371），输出61,998。

R1约31分钟、65轮；R2约21分钟、158轮，题内实际路线和调用次数不同，均提前停止，不能直接把总token比值作为能力保持下降本证据。

## 停止与归档

- 终止宿主runner20816及子进程；停止main e5b41325886e、gateway abcce1de58eb、OTel 5e50d0d9c6df。均未删除；原PMA两个gateway未动。
- 用docker cp从停止容器导出完整/app到`artifacts/literature_transfer_20260913/r2_workspace/app`；这是本次产物，不是参考答案，不挂载未来实验。现场日志在benchmark output，保留。
- 派生数据`artifacts/literature_transfer_20260913/r2_observation_metrics.json`，原audit_r1.py增加run/trial/stop/output参数以复算，无模型或任务代码变更。
- 不复用同run-id、不自动重启。本阶段为工程/行为诊断停止，不接受/冻结新方法。下一只审计重复协议失败，并结合大范围查询、慢请求分析及时性；真实重跑须新确认。
