# 根完成判断合同：最小候选实现

## 研究目的与证据

R9 原始 dialogue D395–397 检查 Hyperlink 的真实分支，D400 却从三项局部
修复推出全部七项目标已验证，D418 最终批准。要求已在输入，不等于被用于判断。
专家入口：`advise/R9_deep_audit_and_next_experiments_2026-09-17.md`。
人工参考已回读：20260907 人工 Fyne 的 014/016 干预原文；前者检查 noop
能否通过测试，后者要求准确起始版本作为对照，不扩张任务。

本候选仅检验根判断指导是否有助于调查选择，不宣称锁定记忆为根因，不宣称
是完整的新方法或论文创新。普通公共构建/测试提醒仍是必须准备的简单对照。

## 启用与实现

- 独立配置 `monitor_root_decision_contract: true`，默认 false，严格布尔值。
- GA 适配层入口 `GA_MONITOR_ROOT_DECISION_CONTRACT=1`。
- 仅允许与 `monitor_pma_memory` 一起启用；无效组合明确报错。
- PMA 作者 process、bank、两阶段及维护阶段交接不变；维护阶段提示不改。
- 判断阶段每次模型调用前先刷新当前宿主提议。有效根提议存在时，以根判断
  合同替换 PMA 的提醒 system 指导；提议消失时恢复原普通指导。
- 原任务、bank、作者拼接的 user 输入及 History 保留，未悄悄删去此前结论。
  因此旧 user 输入中的提醒问题仍可能出现；当前 system 明确其不支配根判断。
  这是保留材料、只改变当前判断职责的对照，不是完整上下文去偏。
- `root_decision_contract_selected` 保存模式、提议 generation、阶段及 system hash；
  每次实际 model_input 保留当次组装指导。哈希不是模型实际消费证据的证明。
- 提议指的是宿主交接，可能是完成、澄清或阻塞；仍由模型读公开消息解释其语义。

## 模型所做的判断

判断准备批准的范围、观察能支持的范围，以及是否有会改变决定的具体缺口。
有缺口时自主选择最小有效观察；不要求先证明错误才能调查。局部修好不代表
全局完成；充分时停止，不把每个未知都当错误，不把耗尽预算当成功。
没有新增 checklist、ID、结构化判断记录或强制测试命令；没有新增调用或预算。

## 作者复用边界

继续使用现有 vendor PMA 作者 process/bank（固定来源见融合实现文档）。
根合同是本地适配候选，不称作者原样机制。未修改作者文件，未引入其他论文
代码或第三位 reviewer。没有改控制动作送达、暂停/恢复或压缩机制。

## 工程验收

在 GenericAgent-main 运行：

`D:\python\envs\ga_bench\python.exe -m pytest tests/test_monitor_root_contract.py tests/test_monitor_pma_fused.py tests/test_monitor_provider.py tests/test_monitor_follow_wait.py tests/test_monitor_completion_settlement.py tests/test_monitor_handoff_validation.py -q`

101 passed（mock 请求，无真实 API）。覆盖普通输入一致、原 bank/工具保留、
根提议中途出现/替换/撤销、真实 provider 类 system 替换和历史保留、配置校验、
既有交接和 completion 控制回归。初次新增夹具遗漏 request_id、未指定 UTF-8，
纠正测试夹具后通过，未为夹具降低生产要求。

## 下一门禁

真实运行尚未启动。候选未晋级。后续在同一 Fyne 开发题和相同预算下与 R9、
简单公共检查提醒比较，记录实际调查、结论范围、误放行/误阻塞、结果和成本。
历史 R9 可用于探索对比，不能当重复配对正式实验。简单对照尚未实现；本次
没有准备或启动多组批次。持久 Judgment Record 仍待这一步行为结果决定。
