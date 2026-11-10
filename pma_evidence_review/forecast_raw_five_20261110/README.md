# P1 “先预想、再保存”五题真实运行（2026-11-10）

执行代码 `3a8c14fdf32f84687d397a44b105bc4431ab5f51`；数据集 `2fd12b88aafdd04a52c298e3940bcb189f9766d6`；Harbor `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`。方法为 `pma-predictive-read-context`，Task 请求配置为 Claude Opus 4.8，P1/P2 请求配置为 Claude Opus 5。Task/PMA 本机 profile SHA-256 分别为 `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e`、`c568aac2b3042f852537a7302bae48e756bbaea74f732ff7e985298d7b2a98e6`（私有 profile 未上传）。每 8 个有效 Task 步骤唤醒一次；Task 总轮次、总时长为 uncapped，verifier 使用各题官方时限。本次是 uncapped diagnostic，不称官方 Agent 限时成绩。

| 题目 | run_id | Task 步骤 | P1/P2 响应 | P1 有公开正文 | read/add | 实际送达提醒 | 原生 reward | 清理 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| kv-store-grpc | `pma-919c9b7efe0c46d7` | 13 | 2/2 | 1/2 | 0/2 | 1 | 1 | 完成 |
| reshard-c4-data | `pma-1b07a3ae276b479e` | 25 | 23/4 | 12/23 | 2/18 | 1 | 1 | 完成 |
| rstan-to-pystan | `pma-7ae56fa5d2394954` | 93 | 74/12 | 11/74 | 8/56 | 9 | 0 | 完成 |
| largest-eigenval | `pma-49ce9b51c01b4e86` | 14 | 15/2 | 6/15 | 1/13 | 1 | 1 | 完成 |
| filter-js-from-html | `pma-757d703e23654e70` | 2 | 17/1 | 8/17 | 1/15 | 0 | 0 | 完成 |

五个 episode 均正常完成 Task、原生评价及所属资源清理；未重跑。`P1/P2 响应`计模型逻辑响应，不能当作底层 HTTP 尝试。P1 的空公开正文不证明模型没有内部预想；公开记录没有据隐藏推理补造说明。Task 请求记录提供了 token 用量，PMA 响应未提供可核实 usage，完整方法费用和底层请求次数均为 unknown。

归档的 `wake_index.json` 将 21 次唤醒逐次关联到当时任务描述、轨迹、P1 公开正文、实际 read/add 参数与回执、P2 结果，以及后续最多 10 个 Task 步骤。完成十步后续窗口的唤醒数依次为 1、2、11、1、0；不足时明确标记。它不自动给预测准确性、信息有用性或提醒采用情况打分。所有 12 条生成的提醒均在下一次真实 `provider_request_ready` 的可见文本中找到精确对应，并有同一调用 ID 的请求尝试和响应；宿主初始 `returned_not_confirmed_in_ga_request` 仅是排队时的暂定状态，不能据此误记为未送达。

有限的行为观察：reshard 在第 8 步提醒后，第 9 步 Task 可见摘要明确提到 memory context 并检查 `compress.py`；rstan 的一次提醒后，下一步转向检查脚本，但本题最终 reward 仍为 0；filter 在 2 步后结束，无提醒，也没有完整十步观察窗。这些相邻事件不能单独证明提醒导致行动或任务成败。与历史版本相邻的得分差异也不能归因于本次 P1 提示：轨迹与历史处理另有变化，各题仅一次。

启动前五题 plan、prepare 和身份检查通过。目标定向离线检查为 89 通过、1 个测试夹具失败：安装的 LiteLLM 1.86.2 不接受旧夹具向 `AsyncHTTPHandler` 传入 `transport=`，失败发生在候选逻辑之前；另外 55 项相关检查通过，包括实际安装的 LiteLLM/Anthropic 离线适配检查。保留原始输出，未宣称全绿。Docker 初次 prepare 时未启动，启动 Docker 后重新 prepare 成功；没有发生模型请求或 episode 重跑。

`PMA_FORECAST_RAW_FIVE_REAL_20261110.zip` 是完整可公开的可见投影，包含五题运行轨迹、P1/P2 请求/可见响应与工具回执、知识库、评价、异常、清理及启动检查；`*.index.json` 逐文件列原件与投影大小和 SHA-256；`*.wake_index.json` 为机械关联的逐轮核对入口。公开包不是原始 HTTP 字节；本机私有原件保持不变。投影排除私有 profile、凭据/端点、provider 私有 thinking/signature、隐藏测试正文；不利结果和格式/工具错误仍保留。实际运行输入未因公开投影而改写。
