# 续接用途边界修复：完整空响应进入笔记校验

专家对公开版本 `524b544` 的审计指出，完整解析但没有可见正文的续接响应会在
provider 的通用空响应检查处重试，无法进入既有的响应归档、`note_text()` 分类和
一次格式恢复。该判断已与本地 `_request_batch()`、`_prepare_continuation()` 接线核对。
这项问题不说明旧 R1 的实际拒绝响应必然为空；原始响应未归档，根因仍未知。

## 本次改动

- 对 `continuation` 和 `format_repair` 用途，provider 将**完整解析**的响应原样
  返回续接层。其余普通 review 的空响应重试规则不变；HTTP 错误和缺少完整
  `message_stop` 的流仍由原传输恢复处理。
- 续接层既有的原始响应归档、停止原因校验、最多一次格式恢复、取消与 deadline
  约束继续生效。空 `end_turn` 得到 `empty_note`；仅 thinking 且 `max_tokens`
  得到 `truncated_note`；空 `refusal` 得到 `abnormal_stop`，不会作为格式问题盲目重试。
- 每份完整响应按 request_id 写入现有 `request_usage` 进度和响应归档；返回续接层
  后进入原有 `usage_records` 汇总。读取成本时须按 request_id 对应两种视图，
  不能将 progress 和上层 usage 简单相加。网络中断时网关未返回的 usage 不在本次
  完整性保证内。

未改根判断候选、PMA bank/阶段、任务调度、模型配置或压缩策略；没有新增调用阶段。

## 验证和边界

新增 provider 请求层回归使用 Anthropic SSE 解析器，只替换 `_request_once()`；
覆盖空正常停止后恢复、无正文截断后恢复、空拒绝响应终止、两次空响应后保持
原 History，以及普通 review 继续走既有空响应规则。核对 request_id、两份
原始归档、两次实际 usage、单次格式恢复和压缩提交。

相关 9 个测试文件合计 **142 passed**，不需要真实 API。该结果证明接缝的确定性
行为，尚未证明真实网关稳定性、R1 原始失败原因或方法有效性。

## 待启动比较

`method_discovery/prepare_root_decision_comparison.py` 现以新 suffix 生成不可覆盖的
清单。已准备：

- `method_discovery/artifacts/root_decision_20260917/fyne_decision_r2_manifest.json`
- `method_discovery/artifacts/root_decision_20260917/fyne_simple_r2_manifest.json`

两组同为 Fyne 2.2 method_dev，同一 `no-network-unix-inference-v1` 隔离、
Claude Opus 4.8 监察配置、500 turns、10000 agent seconds；仅根判断两开关不同。
共同源码 SHA-256：`7358f17141c0b100307ae2a4f058e8f5e536563d302b9848dc91985006ed4e7a`。
状态均为 `prepared_not_executed`。真实启动前仍须做镜像、源码/宿主 hash、
模型连通性和 run-id 预检；未经确认不启动。旧 R1 不重用、不补记 reward=0。
