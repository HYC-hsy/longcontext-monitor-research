# P1 静态子阶段2：评分、日志与源码身份核查

## 结论与边界

本轮无API、无Docker、无真实任务；没有修改生产监察者或提示词。上一静态阶段已提交 `72713a4`，其中CURRENT_CHECKPOINT包含此前积压的恢复记录，不代表这些历史工程在该提交才实现。本轮只新增离线研究工具、测试、哈希清单和本报告。

本阶段完成的是“评分口径有代码依据、日志能证明到哪里、源码身份有哪些缺口”，不是整个P1完成或所有实验已就绪。每阶段Git保存规则已进入AGENTS.md。

## 1. 六题原生评分已核查

仅检查method_dev缓存任务的tests/test.sh评分包装器，不读取隐藏断言、不执行verifier；此信息只供研究者事后评价，不进入任务Agent、监察者或在线运行副本。

|题目|阶段数|权重之和|阶段权重（按原包装器顺序）|
|---|---:|---:|---|
|pyg2.3|12|17|3,1,1,2,1,2,1,1,2,1,1,1|
|fbr2.43|7|8|1,2,1,1,1,1,1|
|ktx0.13|6|10|3,2,1,1,2,1|
|rat0.22|6|11|3,2,2,2,1,1|
|opt4.4|6|9|3,2,1,1,1,1|
|fyn2.2|7|11|2,2,2,1,1,2,1|

共同原生指标为 `sum(weight_i * phase_pass_i) / sum(weights)`，不是通过阶段数/总阶段数。wrapper写 `/logs/verifier/reward.txt` 和reward.json（reward、phases_passed、total_phases），正常走完后exit 0；因此退出码0只证明脚本正常收尾，不能视为任务成功。

本研究拟派生一个明确的二元辅助口径：**全部原生阶段通过**。所有权重为正，所以它与reward精确1对应。不得把该派生指标描述成已核实的论文唯一官方主指标；原生加权分仍完整保留。评分器覆盖之外的真实语义问题不因满分消失。

新增 `paper_scoring_provenance.normalize_reward`：校验reward有限且位于[0,1]、阶段数与任务版本一致、满分与全阶段通过一致；输出success和partial_score。缺字段/NaN/布尔伪数字/版本不符报错，不补0或补成功。此函数不接管运行有效性：环境异常、泄露、终止原因、日志齐全度必须另查；也未验证所有部分分是否与具体通过位向量一致。

`run_ultralong_m12_proofs.py:609`归档 `result.verifier_result.rewards`，同时保留trial_result路径；`reward_not_a_proof_gate`表示工程执行证明不以分数为门槛，不能拿manifest的工程通过当论文任务通过。后续统一表读取原trial和verifier输出，再用上述映射；本轮尚未写自动遍历旧运行的导入器，避免把污染/异配置运行混成新基线。

## 2. 日志指标映射：存在不等于完全可计算

|指标|实际源码/归档依据|能证明什么与缺口|
|---|---|---|
|监察审议次数/时长|agent.py:455，audit/reviews.jsonl的started_at、duration_seconds、action|每次review，不能等同一次API请求|
|监察对话/工具调查|agent.py:222，audit/dialogue.jsonl的timestamp、review_id、event|可回看模型输出与工具使用；读到材料不自动证明理解正确|
|监察请求尝试|provider.py:_request_batch；audit/progress.jsonl与request_attempts.jsonl|请求开始、request_id、重试/空响应/结果；需按请求配对，不把review时长全算生成耗时|
|成功调用用量|agent.py:466，audit/provider_usage.jsonl|保存drain_telemetry的usage；不能据此说包含所有失败费用|
|空响应可能已用token|provider.py:470先发request_usage，再检查response_empty|需检查progress中的usage；仅相加provider_usage可能漏计，失败上游未回usage则未知|
|纠偏提交/交给接口|runtime.py:_pump_outputs与runtime_receipts.jsonl、delivery_feedback.jsonl|handed_to_task_interrupt_interface只证明调用中断接口返回；不是任务已消费、更不是行为采纳|
|任务续接|agent_loop.py:62附近consume_resumable_interruption及后续公开动作|要用任务侧实际续接/工具结果对照建议；本轮未确认统一可直接join的端到端送达时戳|
|任务模型用量|llmcore.py:338–361归一化字段及现有遥测归档|输入/输出/缓存字段已存在；仍需核查旧归档对所有调用的覆盖率和去重关联|
|压缩与额外续接|agent.py:249的pre_compaction_continuation、history_transforms.jsonl|不能只统计普通回答；成功续接用量进入telemetry，异常情况需progress补证|

因此暂不能宣称已实现完整的t0→t4时延表或精确美元统计。下一个离线导入器需先做覆盖率：哪些请求有usage、哪些干预有任务侧响应、哪些时间只能给区间。缺失写null及原因，不用另一类时间戳冒充。

两份usage可能描述同一请求，不能直接相加；优先按progress的request_id整理请求账，provider_usage作为一致性核对/补充。没有request_id的旧记录不能靠金额相同盲目合并。未知失败调用费用不能记为零。

成本比较还需区分provider语义：OpenAI cached_tokens通常作为输入细项；Anthropic输入、cache_read和cache_creation是不同报告字段。保留原始provider字段并按适配定义计算，不用统一“总输入+所有cache”公式。本轮只核查本地字段实现，未调用服务确认账单计费。

## 3. 源码身份：先检测变化，不伪称可回退完整基线

`PAPER_P1_SCORING_SOURCE_SNAPSHOT_20260912.json`记录全部monitor_agent_core/*.py及选定接线/隔离/启动文件的逐文件SHA与集合SHA，也记录评分wrapper身份。生成脚本不导入运行时、不读密钥。

这个清单是**范围明确的工作区指纹**，不是完整可执行快照：不含任务Agent其余源码、依赖、镜像、运行配置。当前工作区仍有前阶段未提交的生产改动；本轮研究提交没有保存那些源码内容。因此不得拿当前HEAD或这个SHA宣称已经冻结整个可运行基线。

旧 `m1_prepare_real_task_batch.tree_hash` 是广泛遍历（仅排除若干缓存/temp），可能把非实验代码或本地配置也纳入身份。它适合原有启动一致性检查，不适合直接当论文发布源码身份。此次不改旧hash，以免旧manifest/启动合同失效。后续冻结应另建显式源码/依赖清单并核查秘密，保留原门禁，两者用途分开。

## 4. 本阶段验收

- 已完成：6题评分包装器检查、原生部分分与派生满分成功区分、错误输入拒绝、逐文件指纹、日志字段—语义映射、缺失项清单。
- 验证：`python -X utf8 -m unittest discover -s method_discovery -p test_paper*.py -v`，9项通过（前阶段5项+本阶段4项）；合成评分与静态文件检查，不是方法有效性实验。
- 未完成：6题离线依赖/镜像实际运行核验；完整可回退生产源码冻结；旧轨迹自动导入和覆盖率统计；PMA接入；正式预算门禁。
- 下一静态子阶段：先用已归档运行开发只读指标导入和覆盖率审计，旧运行仅作日志兼容夹具、不计入干净效果表；同时确定完整基线保存清单。PMA调度适配仍是独立设计选择，不能为了“继续”默认改成同步。

本阶段结束后单独Git提交上述研究文件。无模型/任务启动授权消耗，不因工程测试通过接受任何机制。
