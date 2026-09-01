# C4 Monitor Agent 源码独立化迁移报告（2026-09-01）

## 阶段目标

把已经接入 GenericAgent 的干净监察者，从“运行时隔离但仍复用 GA 内部源码”迁移为完整、可单独演化的 Agent 实现。GA 只保留任务侧事件、可恢复中断和完成边界的薄适配，不再充当监察者的实现底座。

## 最终边界

### 独立监察者核心

`GenericAgent-main/monitor_agent_core/` 自含以下能力：

- `agent.py`：监察者身份、通用工具、持续审议与控制动作；
- `provider.py`：Anthropic Messages 与 OpenAI Responses/Chat 的独立流式客户端、推理内容续接、用量记录和历史恢复；
- `loop.py`：独立工具调用循环；
- `workspace.py`：只读任务证据、可写私有认知和临时分析视图；
- `process_runner.py`：监察者私有分析执行；
- `runtime.py`：独立进程、两层公开轨迹、主动巡查、纠偏输出与完成审计；
- `actions.py`：监察者自己的动作与工具结果类型。

核心包不导入 `ga`、`agentmain`、`agent_loop`、`llmcore`、`mykey`、`research_runtime`、`experiment_conditions`，也不导入 GA 的 GUI、Web、Reflect 或自进化模块。

### GA 适配层

`GenericAgent-main/ga_monitor_adapter.py` 是唯一 GA 专属边界，职责仅为：

1. 创建独立 `MonitorRuntime`；
2. 转发 GA 已公开的边界事件；
3. 把监察者完成结论转换为 GA 的 `CompletionDecision`；
4. 关闭监察进程。

模型配置由 GA 在适配边界解析为普通字典后传入核心；监察者核心不读取 `mykey.py`。任务 Agent 的可恢复强制中断仍属于 GA 侧执行适配，不侵入监察者核心。

## 删除的旧实现

以下根目录实现已被独立包替代并删除，避免双实现和隐式回退：

- `monitor_agent.py`
- `monitor_agent_workspace.py`
- `monitor_controller.py`
- `clean_monitor_runtime.py`
- `process_runner.py`
- `tests/test_monitor_controller.py`

## 验证证据

- 独立核心定向测试：25 项通过；
- GenericAgent 完整测试：327 项通过；
- AST 依赖边界测试：核心包不存在被禁止的 GA 源码导入；
- 干净子进程导入测试：`import monitor_agent_core` 不会加载任何被禁止模块；
- `git diff --check`：无空白错误，仅有 Windows 行尾提示；
- 未启动真实任务，未调用外部模型 API，因而没有新增实验成本或结果污染。

自动化边界测试位于 `GenericAgent-main/tests/test_monitor_core_independence.py`。今后若核心重新引用 GA 内部模块，测试将直接失败。

## 完成条件与限制

- [x] 监察者源码完整存在于独立包中；
- [x] Provider、history、工具循环和 workspace 不再复用 GA 内部实现；
- [x] GA 只通过薄适配器连接监察者；
- [x] 旧的重复实现已删除；
- [x] 确定性与完整回归通过；
- [ ] Anthropic/OpenAI 中转的真实连通和长程任务行为尚未验证；这属于下一次独立真实启动门禁，不能由工程测试代替。

本阶段只证明“独立实现完整且工程可接线”，不声明 M3 候选有效、监察效果提升或真实任务已经通过。
