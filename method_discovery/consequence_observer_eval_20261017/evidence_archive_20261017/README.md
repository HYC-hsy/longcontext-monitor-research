# Consequence observer 三例运行：原始证据补交

本目录只补交 2026-10-17 已完成的六个独立单元。此次归档没有新增模型请求、Task 运行或 evaluator 调用，也没有修改原运行目录、C0/F0 方法、输入、提示或结果。`raw/` 是按捕获原字节复制的可逐文件读取副本；[`CONSEQUENCE_THREE_CASE_PUBLIC_EVIDENCE.txt`](CONSEQUENCE_THREE_CASE_PUBLIC_EVIDENCE.txt) 是可独立在线阅读的 UTF-8 JSON，逐项内嵌 `raw/`、`EVIDENCE_INDEX.json` 和 `PUBLIC_FILE_SHA256.json` 的全文、字节数和 SHA-256。若从 TXT 还原，应验证每项字节数和哈希，不应把它当成新的运行记录。

六个目录按实际执行顺序编号：07/235 C0、F0；14/105 C0、F0；18/6 C0、F0。原计划在 14/105 是 F0→C0，而实际为 C0→F0；原有 `identity.json`、`summary.json` 和结果未重写，也未为此重跑。公开仓库中可定位的先前计划摘要在 [`consequence_v0_cloud_handoff_20261017/README.md`](../../curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/consequence_v0_cloud_handoff_20261017/README.md)；原聊天授权全文未找到可公开的仓库定位，不能以摘要冒充原文。本次用户指令仅授权归档。

每个单元的 `requests.jsonl` 两行分别为 Phase 1/2 实际下界 system、user prompt、tools；`responses.jsonl` 两行是原始内容及工具提议；`result.json/operations` 是实际 PMA 操作回执，`bank_after.json` 是实际保存状态，没有另一个独立的操作回执文件。`provider_attempts.jsonl` 记录每次发送和返回的边界捕获；它不能证明更深层网络重试次数。逐项提议、参数、回执、原始 Phase 2 输出与解析结果的定位见 [`EVIDENCE_INDEX.json`](EVIDENCE_INDEX.json)。所有操作回执标记成功。四个 Phase 2 沉默，两个（07 C0/F0）产生提醒；这不是 Task 投递回执。

六个 `memory_update_status` 的提议长度依实际顺序为 690、768、766、874、366、333 字符；逐字符等于 `bank_after.json/status`，并在 Phase 2 请求中完整出现，均未触发 PMA 的 2000 字符 status 上限。索引分别保存提议、保存、进入 Phase 2 的等同性检查，而非仅作子串证明。其余保存／删除项的参数、回执与最终 bank 也在原始文件中。

原始定位示例：07 的公开 density 函数要求见 `raw/unit_01_07_candidate/bank_before.json` 知识项及同单元 `requests.jsonl:1/prompt`；`dnorm(x, log=TRUE)` 和 `log(func(x_star))` 见同一请求和响应。14 的 `j=180` 位于 `raw/unit_03_14_candidate/requests.jsonl:1/prompt` 的最近工具输出，`0 bytes` 的完整解码失败位于该请求的原任务轨迹/status；两臂 `responses.jsonl:1` 保留模型自己的说法。各臂更多出现位置列在索引中。此处只做定位，不判定建议正确性。

脱敏审查逐字段核对了实际捕获结构；没有发现密钥、认证头、私有端点或其他需删字段。因此公开副本的脱敏变更清单为空，`PRIVATE_FILE_SHA256.json` 以仅含相对文件名、字节数、哈希的原有盘点副本公开。任务文本、模型输出、工具输出、操作参数和错误内容均未为简洁而删改。输入任务轨迹中原有的 URL 和本地路径属于模型可见证据，原样保留。`PUBLIC_FILE_SHA256.json` 按公开副本的实际字节生成。缺口：不存在独立操作回执文件、底层网络重试日志、Task/evaluator 续跑或提醒投递回执；原聊天授权全文未找到公开定位。

原交接 TXT 的先前预期 SHA-256 为 `d4a20037300dab0afd8f8f028d7c49a88807b8382f6337d51dd48db05009c0c`，实际源文件和已提交副本均为 `263ef8fec8900dc11e98364902b13f0a765203681f1e5ca68368e402ef449fe7`，不相等；此前用户已指示继续。交接 JSON 内 37 个文件的声明字节数／SHA-256 与恢复目录实际字节逐一相等，完整期望／实测表见索引 `restored_file_checks`。原两个 ZIP 容器仅是 `source_archives` 身份记录，没有重建同字节容器或声称重新核验 ZIP 容器哈希。

对本公开 `raw/` 用既有 `audit_three_case.py` 作离线只读复核：6/6 单元、12 个已有逻辑调用、12 个已有 provider 边界返回，累计 226,719 输入和 10,486 输出 token；新增真实调用均为 0。该核验不构成语义效果或任务完成证明。完成归档后停止，等待主脑审计。
