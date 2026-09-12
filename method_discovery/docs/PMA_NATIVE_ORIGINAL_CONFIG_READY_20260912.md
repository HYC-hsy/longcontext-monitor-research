# 原模型配置 PMA：离线准备与真实 API 预检

## 本阶段完成范围

用户批准原模型配置，并进一步批准必要的真实 API 检查。已保留作者 Sonnet 4.5 task / Opus 4.6 memory、temperature 0.7/0.3、50 turns、XML、summarize、terminal recording、8步逐步同步触发和 user_turn 注入。没有改作者仓库源码、GA 或 Clean Monitor 的策略。

有两项明确部署差异：OpenRouter 改为现有 CC-VIBE Anthropic 通道；Enroot 改为已验收的 Docker。LiteLLM 请求名分别为 `anthropic/claude-sonnet-4-5-20250929`、`anthropic/claude-opus-4-6`。第三方通道的服务身份不能由模型自述独立认证，因此这是请求配置与接口功能验证，不是供应商身份证明。单次运行并发数从发布批次的12改为1，不改变单题记忆策略。仍不能宣称复现了原论文成绩。

## 改动与验证

|部分|实现与证据|
|---|---|
|原配置加载|pma_native_support.py 加载发布 YAML，只改声明过的路由、无效占位凭据和批次并行数；测试逐字段比较 model/memory 其余配置相等|
|调用计量|同文件旁路包装 task/memory 原 client.call；参数与返回对象不变，异常继续抛出；记录 usage、耗时、actor。只计逻辑调用，内部失败重试不可得用量明确缺失，不冒充完整账单|
|任务生命周期|pma_native_trial.py 接计量并在运行前保存移除 api_key 的实际配置，保留原作者 Agent、终端和事后 Verifier|
|隔离准备|prepare_pma_native_bundle.py 生成独立 gateway/controller 配置：controller 无网络；真实凭据仅 gateway 挂载；Docker socket 仅可信 controller 持有，绝不挂给任务容器。默认命令是测试，不自动做题|
|显式入口|pma_native_entry.py 要求批准标记、具体任务、固定镜像身份和正数时间上限；启动本地 Unix 推理桥，调用原生 trial。完整入口尚未跑过真实题，不据预检声称已验收整个真实生命周期|
|通用依赖层|TaskDependencies.Dockerfile 仅 apt 安装 asciinema 及依赖；FBR 原镜像为 Debian12/root，实装 asciinema2.2.0、python3-pkg-resources66.1.1-1+deb12u2，0升级、2新包，包管理器报告额外1322KB|
|真实终端夹具|preflight_pma_native.py 可执行原作者 agent.setup，然后以固定文件操作代替 agent.run；实际启动 tmux/录像、在模拟Agent结束后上传隐藏夹具评分，全部通过|

每个实现步骤均低于600行代码增删；按配置/计量、请求协议、隔离入口、终端预检、真实API探测分别实现。不是一次混入研究候选。

Linux 原版测试9项通过；宿主 bundle边界测试1项通过。真实断网终端夹具通过，源码资源一致性仍为 memory_agent16项、Harbor167项；评分1.0仅为合成文件检查，不是FBR成绩。控制器夹具峰值280018944字节（约267MiB），仍非完整长程推理峰值。

## 真实 API 结果

路径：作者 LiteLLM → controller loopback bridge → Unix socket → 固定 HTTPS gateway → CC-VIBE。

|检查|结果|耗时|报告input/output token|
|---|---|---|---|
|Sonnet4.5 简短文本|Hello!，通过|6.19秒|77 / 2|
|Opus4.6 自动选工具|record_fact，参数text=Hello，通过|5.43秒|113 / 6|
|Opus4.6 简短文本|非空文本，通过|5.29秒|77 / 16|

3次逻辑调用均通过，输入合计267、输出24；缓存为输入的另列统计，不能重复相加。Harbor/LiteLLM 报告的 cost_usd 合计0.0011015，仅模型价格表估算，不是中转账单。短请求时延不能外推完整PMA两phase延迟和单题成本。

实际请求捕获测试还确认 /v1/messages、模型名、温度和工具协议，经过现有 gateway resolve_request 校验。真实API同时完成了整个Unix链路检查。

依赖出现 Pydantic/LiteLLM 序列化告警；没有阻断解析、工具调用或 usage 返回。未为消除告警擅自更换作者依赖。假HTTP测试在多次短生命周期event loop下还出现后台logging协程告警；真实探测使用单一loop，未见该条。不能因此推定长任务所有异常已消除。

## 可复查产物

- 终端夹具：`bench_runtime/pma_linux_controller/work/native_terminal_r1/result.json` 和同级 `native_terminal_r1-controller.json`。
- 原生源码测试使用冻结控制器镜像，挂载 `bench_runtime/pma_linux_controller/build_r6/scripts` 的审计脚本，未重装传递依赖。
- 推理包：`bench_runtime/pma_linux_controller/native_channel_r1/identity.json`，记录运行脚本SHA与镜像身份。
- 真实探测：`bench_runtime/pma_linux_controller/native_channel_r1/work/api_probe.json`。
- 推理包 `private/gateway.json` 含真实密钥，永不纳入Git、不打印、不挂给controller或任务。运行结束仅清理专用容器和socket卷，保留包与证据。
- 依赖镜像：`longcontext-pma-fbr-deps:20260912-r1`，固定本地ID `sha256:7a6ac7b01515e4ecf96a666f6b8471669eb00d9a9cfdc7e5b765adae63f3f323`。原FBR镜像保持不变。Docker构建提示ARG没有默认值；这里有意要求显式传入任务镜像，不默认选题。

## 下一次真实启动

准备阶段完成；下一步需要具体题目与墙钟预算。建议先用已有 method_dev FBR 做一次原生PMA smoke：50 turns，任务7200秒、事后评价1800秒；它用于确认原版行为与实测成本，不与旧GA结果作严格胜负比较，也不称TB2.0论文成绩复现。FBR依赖准备不是暗中选定正式评价集。

任务材料需复制到本次 bundle/work 的独立目录；trusted controller读取任务配置并在结束后上传原生tests，任务容器本身不得挂载该目录或旧轨迹。调用入口时传具体任务路径、独立输出目录和固定依赖镜像ID。不得用此默认测试compose直接假称真实运行已开始。原生预算与共同GA的500turn/10000秒协议仍分开，后续公平比较另行固定。
