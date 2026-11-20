# 可选 provider 响应旁路留存

此改动仅用于**后续** PMA host worker 的原始 HTTP 响应留存，不补造 1f5adbc4 旧批次缺失的服务响应。默认关闭。仅在受控本机设置 `PMA_PROVIDER_RESPONSE_CAPTURE=1` 和绝对目录 `PMA_PROVIDER_RESPONSE_CAPTURE_ROOT=<受控本机目录>` 时开启；目录不得在 run/output 或 shared spool 下，且每个 run_id 必须全新。worker 写入 `<root>/<run_id>/request-...response.bin`（非流式）或 `...stream.bin`、`...chunks.jsonl`、`...events.jsonl`（流式）。流式事件以原始字节的 base64 逐序存放，不重新消费网络流；原始字节不进入公开归档。run 私有目录中、普通 `archive/` 之外的 `provider_capture_status.jsonl` 只记关联和状态；开启失败会另记 `unavailable`，采集失败记 `failed`，不会改变模型请求、重试或工具循环。Task 进程环境剔除这两个开关和路径。

状态行包含 run、wake、call_sequence、request_index、attempt_in_call、可得 response ID、出站 model 和 `thinking`/`output_config`/`reasoning_effort`/`temperature` 的**存在性与值**、HTTP 状态、字节数和 SHA-256。`reasoning_field_presence` 是对已捕获响应字节的字段观察：`present`、`absent`、`null` 或解析／不完整时 `unknown`；它不证明服务内部是否思考。`capture_status=complete` 是本层响应字节捕获完成，不代表模型调用或 Task 成功。中途关闭或流失败是 `incomplete`/`failed`。服务 response ID 只从捕获内容中取，缺失为 null，不用请求 ID 伪造。

旁路代码不读取或记录认证头，不修改 response body、流模式、请求参数或上层解析。原件可能含签名、私有推理、任务私密信息和其他不可公开内容；须在本机限权保存。公开投影应由独立审查者按字段/片段最小脱敏，去掉 API key、Authorization、Cookie、端点、签名、provider 私有 thinking 及隐藏测试正文；保留来源哈希和脱敏范围，不能把公开副本说成原始 HTTP 字节。本次只提交代码、测试和说明，未启用真实采集、未生成原件。

本地无模型测试覆盖响应含推理字段、无字段、显式 null、两次重试的关联、采集故障、流式顺序和单次消费，以及开启/关闭/故障时请求、公开响应和工具调用的一致性。`httpx.AsyncClient.send` 是本次已知 Anthropic `/messages` 路径的接缝；其他 HTTP 路由不会保存 body。若未来适配器转用别的发送入口，需单独验证覆盖率，不能根据本旁路存在就声称全量捕获。
