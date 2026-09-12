# 本轮优化：停在真实启动前

## 已完成与版本

- `d77b992`：研究审计，MEMORY_ASYNC_RESEARCH_AND_OPTIMIZATION_20260913.md。下载并核对 DPT-Agent、async-control、async-deep-agents、SimpleMem；逐项记录源码身份、真实实现、可借鉴部分与不可直接迁移部分。
- `ba1fe69`：容量续接工程修复，MONITOR_CAPACITY_EXCHANGE_REPAIR_20260913.md。完整工具交换可退休，不再因当前 review 过长而无法压缩；失败显式终止，避免下一次唤醒继续膨胀。
- `aed4328`：可关闭的请求时效感知、原子 file_read 尾部读取及完整开关透传。详见 LIVE_AWARENESS_IMPLEMENTATION_20260913.md。提交包含扩展回归的旧断言修订与 worker 故障验证。

不是 PMA 母体改造，没有第二个监察模型，没有每轮同步审批，没有新增领域规则或第三层语义事件归类。研究仍围绕表示遗漏、错误闭合，以及状态依据如何支持有效恢复。混合同步/并发是保留的后续候选，不在本轮偷偷加入暂停策略。

## 最终工程验证

- GenericAgent tests/test_monitor*.py + tests/test_clean_monitor*.py：**256 passed**。
- long_context_bench 的 test_isolated_transport.py 与 test_run_ultralong_m12_proofs.py：**62 passed**。
- `git diff --cached --check`：通过。候选步骤代码及测试新增删除共 260 行，低于 600 行。
- Docker Engine 29.6.1；固定 Fyne 镜像存在，ID 为 `sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`。E 盘检查时可用 51,928,838,144 字节（约48.4 GiB）。现有两个 PMA gateway 未改动或清理。
- 使用真实 runner 的 `--preflight-only` 成功：任务 tree `928e4d98926e9c6038f2538ec960be19fa1fb199bfc11f06e3fe01a7d50259d6`；GA 源码 `fe7bb4167d02af34f3baf8d2b519ec0885a4f964e56c94d459adb3291be7dc73`；Harbor 三项补丁 applied。
- 预检显示 allowed_hosts 是共享身份报告中的旧字段，不是此次网络权限。manifest 固定 `no-network-unix-inference-v1`；执行路径隔离时不添加这些公网允许项，测试保留禁止公网回退、禁止历史分支挂载的断言。
- 本轮 **零模型 API、零真实任务启动**。实时服务状态未重新验证，因此不能保证启动时中转可用。

## 已准备的单次实验

文件：`method_discovery/artifacts/live_awareness_20260913/fyne_r1_manifest.json`，状态 `prepared_not_executed`。

- task：`roadmapbench:fyn-2.2.0-roadmap`，method_dev。
- run：`clean-monitor-fyn-2.2.0-roadmap-live-awareness-20260913-r1`。
- condition：Clean Monitor，active working context + live awareness，其余旧候选与 PMA 关闭。
- 任务模型 Claude Opus 4.8；监察者 GPT-5.6-sol high，均沿用上一轮配置。
- 500 turn / 10000 秒（2小时46分40秒）任务预算；模型失败恢复不延长整个任务预算。
- 原题、原镜像、无网络任务容器、固定推理通道、在线无 native checker；事后才评分。禁止挂载本轮研究源码库或旧任务轨迹。

先看容量是否不再重复失败、监察是否看到纠偏后的新行为、能否及时提出具体纠正、是否依旧长时间调查旧材料及重复开大清单。同时记录 task/monitor 分开用量、调用、延迟、wall time 和可获得费用。上一轮89分12秒仍未完成，监察成功调用约2092万输入 token；不能承诺本轮低成本或限定时间内成功。中转计费规则未知，不编美元预测。若语义续接失败或持续无效重复，保留失败与归档，不自动修改规则并启动下一题。

历史对照只能帮助诊断。容量修复与时效候选相对上一轮都变化，不能单独归因。需要共享容量修复、关闭 live awareness 的新对照才能辨别独立收益；此次仅准备一条分支，未自动授权追加对照。

## 尚需实验证明，而非继续静态补丁

压缩后认识是否保真、时效提示是否被正确消费、主动工具是否更及时、整体任务质量和成本是否改善，均未确认。tail 仍扫描全文件以保留 hash；请求期间模型延迟仍存在。没有声称全部问题解决或最终机制已冻结。下一动作是用户确认后启动以上单次实验；不自动重跑旧队列。
