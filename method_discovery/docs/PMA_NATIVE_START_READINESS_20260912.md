# 原版 PMA 单次启动准备审计

## 本轮结果

Linux 控制器已可用，但尚不能直接启动真实复现。本轮只检查已有代码、协议与镜像；零模型 API，未启动任务 Agent，也未修改作者源码、GA 或监察策略。

Docker Engine 29.6.1 正常。以 `--network none --read-only --entrypoint /bin/sh` 在两份现有镜像中运行 `command -v`：

|镜像|bash|tmux|asciinema|python3|
|---|---|---|---|---|
|FBR 2.43|/usr/bin/bash|/usr/bin/tmux|未找到|/usr/bin/python3|
|Fyne 2.2|/usr/bin/bash|/usr/bin/tmux|未找到|/usr/bin/python3|

最后一条 python3 查询成功不能代表前面所有依赖齐全；以逐项输出为准。检查容器均自动退出，最终 docker ps 为空，没有拉取或清理镜像。

精确镜像身份：
- FBR：`znpt/roadmapbench-fbr-2.43.0-roadmap@sha256:ec14ff1dfcf49e75a9b4c611b3da4b71fc777cd533592512d447b4352b5082c8`
- Fyne：`znpt/roadmapbench-fyn-2.2.0-roadmap@sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`

## 确定的准备缺口及处理方向

1. **终端录像依赖**。作者 `external/harbor/src/harbor/agents/terminus_2/tmux_session.py:68` 会在录像开启且 asciinema 缺失时尝试安装，包含 apt/pip 联网路径。在断网任务中不可依赖这一步成功。应在研究者准备阶段构建可审计的依赖层，保留原录像开关；不得给执行中的 Agent 恢复公网。尚未构建该层，也未实际运行 setup，所以此处是源码加依赖检查确认的风险，不是已观察到一次 setup 失败。
2. **原生推理接线**。作者 ModelConfig/MemoryConfig 均公开 api_base/api_key；runner.create_agent 原样传给 LiteLLM。现有固定端点 Unix 网关可作为传输基础，但尚未验证 native LiteLLM 的实际请求路径。应保留调用和解析机制，只配置受控推理入口，并做零 API 请求捕获测试。原版经 litellm.acompletion 调用，不能把此前 GA Responses 测通直接当成这条链路测通。
3. **全量成本**。memory_enabled_agent 将 task Chat 的累计 token/cost 写入 AgentContext；memory trajectory 保存提示、操作、注入和 bank，但没有相应完整 usage 字段。应旁路记录 task/memory 两侧调用的返回 usage、耗时与异常，不改变提示和返回内容；供应商未返回的费用记未知。不能拿 task_usage 冒充 PMA 总成本。

上述三项是启动准备工作，不是新的论文机制。尚未实施，避免在模型/比较轨道未明确时为错误路线继续接线。

## 启动前需要用户决定的比较轨道

- **作者原配置检查**：完整原生 Terminus2+PMA，发布 YAML 的 Sonnet 4.5 task / Opus 4.6 memory、temperature 0.7/0.3、50 turns。用于确认原版能运行；要宣称原论文成绩复现还需要原 TB2.0 数据、重复次数及协议。不能把在 Roadmap 的一次运行称为原论文效果复现。
- **共同 GA 比较**：保留原核心机制与同步注入，但任务底座为 GA；现有准备脚本提议 Opus 4.8 task / GPT-5.6-sol-high memory、500 turns。这是明确命名的 GA adaptation，不能代替作者原配置检查。

两者都可做，但不得静默混成一条实验。建议先以作者模型配置做小规模原生运行检查，再进入共同 GA 控制比较。模型可用性尚未调用 API 确认；不可擅自降级或换模型。新增 TB2.0 题、具体题目和预算仍需批准。

本轮停止于上述协议选择，不把 Linux 环境工程验收等同于方法效果或完整真实启动准备完成。
