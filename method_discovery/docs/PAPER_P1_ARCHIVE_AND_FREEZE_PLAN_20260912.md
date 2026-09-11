# P1 静态子阶段3：旧归档指标覆盖率与完整基线保存范围

## 本轮完成什么

新增只读 `paper_archive_coverage.py`：固定读取Fyne三条旧运行的progress、provider_usage、runtime_receipts，以请求ID归并、检查缺失/冲突，输出聚合数与文件SHA。没有读取提示正文后对其评分，没有读取隐藏答案，没有API或真实执行。

三条样本固定为tool-feedback基线R1、处理R2、发生传输失败的feedback-B R3，用来检查正常/异常记录兼容性；不是挑选成功方法，也不是完整历史普查。处理R2曾读取目标源码，明确不具有干净效果证明资格；三条均不加入新隔离条件的效果表。

## 覆盖率结果

|日志夹具|请求开始|请求结束|有输入/输出用量|覆盖率|接口交接回执|回执含timestamp|
|---|---:|---:|---:|---:|---:|---:|
|tool-feedback base R1|101|100|95|94.1%|10|0|
|tool-feedback treatment R2|79|79|77|97.5%|4|0|
|feedback-B R3|29|28|20|69.0%|2|0|

分母是有唯一request_id的request_started，分子是同ID同时有非负整数input_tokens、output_tokens；重复usage不重复相加，冲突usage排除并报告。覆盖率是记录覆盖率，不是API成功率或方法成功率。

已知用量：base R1为10,630,820输入/10,317输出；treatment R2为10,137,953/21,281；B R3为1,121,969/1,837。三条中progress已知字段之和与provider_usage一致，不能把两份相加。B R3有21次request_usage事件但只有20次含完整输入输出，一条空字典不能算完整记录。

**没有发现两份日志对已知token互相矛盾；发现的是完整费用不可由它们直接还原。** 未返回usage的请求可能没有产生计费，也可能已计费，不能据此断言欠记多少美元。脚本将dollars、任务Agent用量、行为采纳率及端到端投递时延保留null。

base R1和B R3各有一次开始没有对应结束，说明归档尾部存在未配对请求；仅靠该字段无法判断当时仍在运行、进程被终止还是最后记录未落盘。此次不补写历史事件，也不据此创建工程补丁。

16条接口交接回执均无独立timestamp，所以不能直接计算精确t3。结合任务端公开事件或其他日志可能重建部分时间区间，尚未验证；不宣称绝对无法恢复。接口回执不是行为采纳，下一步若做恢复指标仍需对照后续行动。

## 工具边界与测试

工具逐行读JSONL，输出文件是否存在、坏行行号、SHA；没有文件的计数只能解释为“读到0条”，必须结合present=false，不解释为无活动。相同request_id重复usage去重，矛盾记录不择有利值。工具不输出原始消息/密钥。

新增5项合成测试：失败请求缺用量、重复去重、冲突排除、接口不等于采纳、缺文件非零费用。与前阶段合计14项通过；实际三条归档成功解析，原文件只读。原始统计保存于 `PAPER_ARCHIVE_COVERAGE_20260912.json`。不存在研究机制晋级结论。

## 完整运行基线怎样保存

现在的阶段Git提交可以回退研究工具，但不能称为全部运行底座已冻结。以下是保存范围与验收清单；不执行git add .，不把历史代码积压伪装成当前阶段实现。

|保存层|具体范围|保存/核验方式|
|---|---|---|
|独立监察内核|GenericAgent-main/monitor_agent_core全部运行.py；对应tests|源码内容入Git，包括未跟踪的advice_basis/feedback_focus/handoff_validation/inquiry；候选关闭不代表模块可遗漏|
|任务侧运行与桥接|ga_monitor_adapter.py、agentmain.py、agent_loop.py、ga.py、llmcore.py、task_interruption.py、research_runtime.py及实际导入依赖|先核查导入闭包，再保存；不要只存新adapter而遗漏任务侧依赖|
|Harbor/隔离|adapters/harbor_ga_agent.py、isolated_setup.py、isolated_transport.py、failure_snapshot.py；scripts/isolated_run_bundle.py、run_ultralong_m12_proofs.py及其运行依赖|源码与回归测试一同入Git；不能仅存哈希而不存源码|
|准备入口|clean_monitor_prepare_real_task_gate.py、prepare_tool_feedback_run.py、m1_prepare_real_task_batch.py、m3_prepare_real_task_gate.py、R0协议|虽然有旧M1/M3文件名，当前入口仍导入它们；暂不重构清理以免引入新行为|
|运行材料|实际复制的assets、plugins、memory等必要文件|逐文件确认来源、必要性和是否包含历史认识；不能无条件纳入干净基线|
|依赖与模型配置|依赖清单、Python/包版本、模型名/等级/协议/超时、候选开关|非秘密配置需固定；mykey及真实token不入Git，使用无密钥模板与外部注入说明|
|容器与评价身份|镜像digest、公共instruction及评分版本SHA、隔离profile|Git保存身份清单，不提交镜像/隐藏答案/运行垃圾；离线依赖可用性另验|

### 一个需核查的真实边界

实际 `isolated_run_bundle.build_bundle` 会复制根目录除mykey外的所有.py，并复制assets/memory/plugins/monitor_agent_core/reflect/ga_cli/frontends等存在目录。memory分支复制顶层.py/.md/.txt，文件名清单包括global_mem.txt、global_mem_insight.txt等。**扩展名过滤并不能证明它们都是冻结通用SOP。** 本轮只列文件名、未审读这些内容，因此不能断言已泄露，也不能未经核查将全部材料称为干净通用知识。

这属于运行输入身份/潜在历史污染核查，不是要求现在重写监察工具或记忆机制。正式干净基线冻结前，必须检查这些实际挂入材料，明确保留名单；若需删除或改变运行输入，应单独说明比较影响并获确认。现有已保存隔离代码仍禁止公网访问，但网络隔离本身不证明本地输入没有旧知识。

## 下一步与停止点

本子阶段完成，独立Git保存。没有API、Docker、生产修改；单步新增代码及测试约200行，低于600。

下一步优先完成“实际运行副本材料审查与完整源码保存清单”：它是公平基线冻结的前置条件，不能用继续调监察提示绕开。然后才把非秘密运行配置与完整内容保存为一个明确的工程基线。若只是明确遗漏文件可局部补齐；若涉及改变任务可见知识或删除运行能力，按重大决策门禁报告。

PMA接入、任务Agent用量自动汇总、端到端行为指标与正式预算控制仍未完成，不因统计脚本可用而声称可以正式做效果比较。
