# 两个连续上下文 PMA 版本：GitHub 交付与四次实验指令

## 源码身份

- 仓库：`HYC-hsy/longcontext-monitor-research`。
- 独立分支：`research/pma-continuous-integrity-20261107`。
- 真实 GitHub 基线：`507ed5b7264a80bca11a5a2dc6b2e03d658e8fac`，根树 `3d71d517597fb833a1c5fe665d59274cbf25f449`。
- 本次源码来自已做工程验证的本地 `c3bcb4f2cbc30e7cbb3ba2d6bf1ce4a73cb2560d` 累计修改。远端提交直接建立在上述真实 GitHub 基线树上，不上传局部检出的本地父提交。
- 发布包含源码、合成测试与说明；不含生成的测试日志、模型请求载荷、凭据或私有实验数据。旧分支、旧结果、开发线程不改。

两个入口同时存在于同一发布版本：

| 方法 | candidate |
| --- | --- |
| `pma-predictive-context` | `pma_predictive_context_v1` |
| `pma-predictive-read-context` | `pma_predictive_read_context_v1` |

本文件是交付/执行说明，不代表已经运行四次实验。真实运行仍等待用户明确启动指令。

## 代码修复与不变项

1. 两个连续版本的 P1/P2 异常都明确失败，不能记成正常 no-intervention。异常回执会解除 actor bridge 的等待，worker 保留失败阶段。
2. history 压缩只修正记录的 `changed`、计数和哈希，不改压缩策略、阈值、计数器、保留规则或提示。
3. GA 合成可见摘要保留原文、原位置和原有标签。PMA 看到的同一文本不增加标签；来源仅在不进入模型输入的审计字段中记录。
4. 两个方法保持独立身份和原调度。新查库版仍只在 P1 自主调用 `memory_read` 时查库/续接；P2 和初始/每8步唤醒策略不变。

## 获取独立工作区

在完整仓库中执行，保留当前工作区和分支。下面目录名须为空且未被使用：

```sh
git fetch origin refs/heads/research/pma-continuous-integrity-20261107:refs/remotes/origin/research/pma-continuous-integrity-20261107
git worktree add --detach ../LongContext-pma-repaired origin/research/pma-continuous-integrity-20261107
cd ../LongContext-pma-repaired
git rev-parse HEAD
git status --short
```

把 HEAD 与交付消息中经远端回读核验的完整提交 SHA 对照。后续四次全部固定该 SHA；不要四次之间自动拉取/切换源码。使用目标电脑已有的受支持运行环境与本地配置，不上传或复制密钥到仓库。

## 运行前检查

- 在完整工作区重跑已有无模型工程检查和相关回归，核对 actor/PMA 源码清单、运行配置及 profile 哈希。
- 本地相关套件已通过181项测试和151个 subtests，含39项本次回归。局部检出的全仓尝试仍有27失败/23错误，与未改基线的失败测试身份一致，主要涉及缺失的源码、依赖和 Git 对象。不能把它称作完整目标环境全绿。
- 两种方法必须使用相同的 dataset/Harbor 版本、actor 和 PMA 模型/profile、模型参数、明确的时间/轮数/成本预算及 verifier 策略。不能由旧日志猜测当前参数或静默改限额。
- 对两个方法重新生成/核对 source identity，不能沿用旧证书。两个 source manifests 均包含这次修复的 `event_spool.py`。
- 使用全新 output/run ID，不覆盖旧结果。真实运行须在用户可见的后台终端显示运行状态。
- 完整目标环境检查、源码/配置固定、用户启动授权，三者都满足后才执行下一节。

## 四次实验

以下把每个方法的两个任务串行执行，共四次。`experiment.local.json` 是目标机器已核验的本地配置文件；`UNIQUE` 应替换为本次唯一标识。两条命令使用同一配置和同一提交，仅方法及输出目录不同。

```sh
python -m experiment_runner run --config experiment.local.json --method pma-predictive-context --task rstan-to-pystan --task nginx-request-logging --output runs/context-repaired-UNIQUE
python -m experiment_runner run --config experiment.local.json --method pma-predictive-read-context --task rstan-to-pystan --task nginx-request-logging --output runs/read-context-repaired-UNIQUE
```

若先做无模型计划检查，使用独立的输出 JSON 文件：

```sh
python -m experiment_runner plan --config experiment.local.json --method pma-predictive-context --task rstan-to-pystan --task nginx-request-logging --output context-plan-UNIQUE.json
python -m experiment_runner plan --config experiment.local.json --method pma-predictive-read-context --task rstan-to-pystan --task nginx-request-logging --output read-context-plan-UNIQUE.json
```

不要把 `plan` 的完成当成真实运行授权或效果证明。一个 slot 失败时按配置原有策略停下/记录，不自动重试已接受的真实任务。

## 结果要求与已知风险

四次分别记录真实源码 SHA、method/candidate、配置/profile/dataset/Harbor 身份、run ID、原任务、终态、P1/P2 调用与错误、提醒是否进入 actor 请求、耗时/token/可得费用、最终改动和官方 verifier。P1/P2 故障计为故障，不能归入 no-intervention。

查库版可能有额外 P1 调用，没有新加固定内部调用上限；history 的名义阈值不是硬上限。这些是保留的设计，不在本次记录修复中擅自改变。完整 PMA 每调用公开响应/回执/用量审计仍有既有缺口，不能虚称完整费用对照。两题每条件一次只能作为描述性对照，不能证明统计优越性。
