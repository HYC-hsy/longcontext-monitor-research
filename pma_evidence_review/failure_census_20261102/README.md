# GA20 与后续 PMA 既有运行问题统计（2026-11-02）

## 结论与统计口径

本轮只审计已有公开可见轨迹和原生评价摘要，未调用模型、运行 Task、评价、修改提示或方法。目的是先确定发生了什么，而不是证明任何新设计有效。

- GA20：20个不同题目的20次GA-only运行，9次reward1、11次reward0。没有外部PMA P1/P2，Actor自身checkpoint不是P1。
- 后续PMA：本轮已取得并复核的14次有评价运行，覆盖4题，其中SQLite11次，另OCaml/RStan/Circuit各1次。4次reward1、10次reward0；其中1次在首次实际动作前工程异常。其余13次正常终止，4过9零。
- 另有2次公开RStan已启动但Docker异常、没有评价的尝试，不当作0分；未启动准备失败、reviewer-only、P1-only不计Task。
- 另列最早SQLite公开包尚未纳入本轮逐轨迹复核、bf96 SQLite私有仅报告、被用户中止旧组。故14不是声称所有历史实验总数。
- 运行与题目是不同分母。下列语义类别可重叠，统计是已确认实例的下界，不是穷尽所有错误，也不是每个零分的唯一根因。

## GA20：先剥离工程中断，再看记忆证据

5次终端provider错误：09、15、16、17、18。其中16原生通过，另外4次零分。11个零分中，剩余7次不是provider终端错误：03、04、07、08、11、13、20。

- 强局部历史遗漏链2题：07 RStan、11 Circuit。早期正确要求存在；后期实际请求不含；后续出现违约或错误复述。并不证明它们是整题失败的唯一原因。
- 混合链1题：08 Git合并。部分要求后期被压缩掉，但主动绕过Git更早就发生，不能全归遗忘。
- 已有信息仍可见却未正确使用：03算法搜索、04验证范围、12解释器选择、15执行器诊断等。它们不支持“只要扩大记忆就能解决”。
- 13缺少自测，20早期输入保全出错，均没有长历史遗忘链。
- 成功案例也有恢复中的错误，不能以reward1当摘要忠实性的证明。

[GA20原归档](https://github.com/HYC-hsy/longcontext-monitor-research/raw/918bcb99d28a70997e73450168a6c00cb20e1c12/experiment_runner/ga20_evidence/GA20_FINAL_VISIBLE_20261030.zip)。下表轮次包括最终无响应的请求；逐事件证据见 RUN_LEDGER.json。

|序号|任务|reward|轮次|provider终端中断|观察到的问题/结果|
|---:|---|---:|---:|---|---|
|01|git-leak-recovery|1|9|否|完成并通过；未确认重要记忆遗漏。|
|02|git-multibranch|1|20|否|推送/部署/HTTPS验证后通过；最后root用户git检查报权限不抹去此前验证。|
|03|feal-linear-cryptanalysis|0|36|否|算法未解；局部搜索被夸为全范围搜索，相关材料仍可见。|
|04|query-optimize|0|10|否|只验证抽样行却声称前105行一致；原生零分精确原因未公开。|
|05|mcmc-sampling-stan|1|21|否|通过；环境失败逐项恢复，divergence警告已看到，不能称遗忘。|
|06|fix-ocaml-gc|1|23|否|修GC并通过；构建超时后检查存活进程，持续追踪结果。|
|07|rstan-to-pystan|0|58|否|原输出合同后期从请求消失，发明另一组输出并称原要求；另有主动改用不合规方法。|
|08|merge-diff-arc-agi-task|0|31|否|主动绕过Git，后期部分分支要求消失；只完成文件处理却宣称完成。|
|09|break-filter-js-from-html|0|19|是|曾误把空输出/exit0当测试成功，后纠正；最终服务中断。|
|10|nginx-request-logging|1|21|否|依赖/构建失败后正常换策略并通过。|
|11|circuit-fibsqrt|0|176|否|原语法后期不在请求，写错语法后回读恢复；算法仍错误。|
|12|multi-source-data-merger|1|15|否|已知解释器差异仍在近期输入，却误用环境；次轮自恢复并通过。|
|13|filter-js-from-html|0|2|否|仅写文件即完成、未自测；原生0/2，具体缺陷未知。|
|14|largest-eigenval|1|30|否|早期算法失败被保留，换路线后通过。|
|15|make-mips-interpreter|0|201|是|反复误用仍可见警告，把异常执行总结为正常；最终服务中断。|
|16|kv-store-grpc|1|12|是|安装/后台服务探测后服务中断，但原生通过。|
|17|sanitize-git-repo|0|2|是|探索一轮后服务中断，尚不足判断记忆机制问题。|
|18|build-pov-ray|0|4|是|源码查找早期遇浏览器/地址问题后服务中断。|
|19|reshard-c4-data|1|22|否|约束保留、自测后通过；局部笔误不构成主失败。|
|20|db-wal-recovery|0|7|否|未先保全WAL就打开原数据库，之后WAL消失；早期操作问题，非已知警告遗忘。|

## 后续PMA：运行与实际提醒

14次共412次逻辑P1、412次逻辑P2请求，实际提醒送达33次。逻辑调用不等于底层HTTP次数，送达不等于有益。

- 8次运行没有任何提醒。其中1次是JSON协议17/17拒绝，1次是首轮后bridge异常，剩余6次是正常运行中全部合法不干预。
- 这6次正常全静默运行全部为SQLite，共95次P2选择；其中2次任务通过、4次零分。不能把沉默都当漏提醒，也不能将成功归功于提醒。
- 另6次运行确有送达，包括旧合成提醒3次运行的15/4/7条，及OCaml1条、RStan2条、Circuit4条。新旧轨迹、任务、提示和审核均不同，不据频率差异作因果比较。

|任务|run_id|方法说明|reward|P1/P2|实际提醒|原归档|
|---|---|---|---:|---:|---:|---|
|sqlite-with-gcov|pma-56b78b0c9cd546be|原合成提醒＋原v4审核|0|32/32|15|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/221c3bd63d2ce569432a0d7911877dece028b809/pma_evidence_review/diagnostic_packages/PMA_V4_REVIEWER_R1_SQLITE_TWO_REAL_TASKS_20261031.zip)|
|sqlite-with-gcov|pma-770994a4f5cc48a9|原合成提醒＋r1审核|0|14/14|4|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/221c3bd63d2ce569432a0d7911877dece028b809/pma_evidence_review/diagnostic_packages/PMA_V4_REVIEWER_R1_SQLITE_TWO_REAL_TASKS_20261031.zip)|
|sqlite-with-gcov|pma-cad24bdee18740bf|原合成提醒＋r1审核（选择实验旧组）|0|22/22|7|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/1f63a2c0f74fc41d3c6f91946d70da0008676d67/pma_evidence_review/diagnostic_packages/PMA_VERBATIM_SELECTION_SQLITE_TWO_REAL_TASKS_20261031.zip)|
|sqlite-with-gcov|pma-b99ec7e899be4eb2|JSON原文选择＋r1审核|1|17/17|0|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/1f63a2c0f74fc41d3c6f91946d70da0008676d67/pma_evidence_review/diagnostic_packages/PMA_VERBATIM_SELECTION_SQLITE_TWO_REAL_TASKS_20261031.zip)|
|sqlite-with-gcov|pma-d20b47d2d9684daa|标签原文选择＋r1审核|0|13/13|0|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/11fcbd65e11ba66cd1514a5d2e55ccaf4f2bba25/pma_evidence_review/diagnostic_packages/PMA_TAG_SELECTION_SQLITE_FIRST_REAL_TASK_20261031.zip)|
|sqlite-with-gcov|pma-4e9d4cff85244e57|E/X执行关联审核＋标签选择，首次桥接异常|0|1/1|0|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/6a4d76b242720b355d5ea16f80b13d493b71cf83/pma_evidence_review/diagnostic_packages/PMA_EXECUTION_LINK_SQLITE_FIRST_TASK_20261101.zip)|
|sqlite-with-gcov|pma-c3a3338baa4e4d0e|运行边界修复＋E/X审核＋标签选择|1|18/18|0|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/667c90957657be89a673c4cc3ee89e5a7aca2fc0/pma_evidence_review/diagnostic_packages/PMA_RUNTIME_BOUNDARY_SQLITE_REAL_20261101.zip)|
|sqlite-with-gcov|pma-17ded442e35c47f5|GAP/近期轨迹IO修正＋E/X审核＋标签选择|0|17/17|0|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/0aab5a15c6818d7078413c5175ecb3a8612d389d/pma_evidence_review/diagnostic_packages/PMA_GAP_IO_DEPLOYMENT_SQLITE_REAL_20261101.zip)|
|sqlite-with-gcov|pma-c818075eb46b4272|一阶段范围提示优化＋关闭审核＋标签选择|1|17/17|0|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/1d7eb456203ba86b904b206202c7987702f188ee/pma_evidence_review/diagnostic_packages/PMA_NO_REVIEW_SQLITE_REAL_DIAGNOSTIC_20261101.zip)|
|sqlite-with-gcov|pma-87f5c8cf56124b29|P1/P2对齐压缩组合提示＋关闭审核＋标签选择|0|16/16|0|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/aa482e89da0ded3a3e55da71b72d6bec08487136/pma_evidence_review/diagnostic_packages/PMA_ALIGNED_P1_P2_SQLITE_REAL_DIAGNOSTIC_20261101.zip)|
|sqlite-with-gcov|pma-740db27b2d4b4ee6|P1工具精简恢复PMA方式＋P2职责最小修正＋关闭审核|0|14/14|0|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/d9837cd221bb7ae2d1c90cdd0033d94dc328d2cc/pma_evidence_review/diagnostic_packages/PMA_P1_LEAN_SQLITE_OCAML_REAL_DIAGNOSTIC_20261101.zip)|
|fix-ocaml-gc|pma-628546435058411d|P1工具精简恢复PMA方式＋P2职责最小修正＋关闭审核|0|49/49|1|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/d9837cd221bb7ae2d1c90cdd0033d94dc328d2cc/pma_evidence_review/diagnostic_packages/PMA_P1_LEAN_SQLITE_OCAML_REAL_DIAGNOSTIC_20261101.zip)|
|rstan-to-pystan|pma-0df5d41e7d4049c2|bank-display条目呈现＋标签选择＋关闭审核|1|30/30|2|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/2fd7f818c659adb7d16918fe35c9fdc62ab77c7a/pma_evidence_review/diagnostic_packages/PMA_BANK_DISPLAY_RSTAN_CIRCUIT_REAL_DIAGNOSTIC_20261102.zip)|
|circuit-fibsqrt|pma-4a1d5d3e5ed349e0|bank-display条目呈现＋标签选择＋关闭审核|0|152/152|4|[包](https://github.com/HYC-hsy/longcontext-monitor-research/raw/2fd7f818c659adb7d16918fe35c9fdc62ab77c7a/pma_evidence_review/diagnostic_packages/PMA_BANK_DISPLAY_RSTAN_CIRCUIT_REAL_DIAGNOSTIC_20261102.zip)|

## 机制问题清单：按运行去重的确认下界

这些标签可以重叠，不能相加；分母是上述14次运行，检查覆盖程度见 ISSUE_EVIDENCE.json。较早5次采用关键末轮与最终库的定向复核，其余结合已有逐轮深审，未对所有操作重新打分。不存在“9/14就是稳定错误率”的推论。

|已确认现象|至少涉及运行数|具体含义与例子|
|---|---:|---|
|失真或依据不足的内容实际入库|9|当前shell成功扩大成全局PATH完成；推测成为根因；源码顺序倒置；旧输出充当现况。|
|GAP实际删除依据不足或理由不成立（全部SQLite）|6|删PATH缺口只靠当前会话成功；编译器尚未确认即关缺口；用“仍不可用”的证据支持删除。|
|状态更新被拒后继续保留旧状态|6|事实是沿用旧状态；并非六次都误拒，不能直接统计为六次有害审核。|
|已有新证据却保留陈旧/冲突记忆|4|OCaml旧成功/失败说法、RStan错误fit结构与正确axis并存、Circuit旧gate计数、审核返工写回旧编译中状态。|
|迟到或重复既有计划的已送达提醒|3|OCaml重复Agent已在执行的路径；RStan/Circuit发现问题之后才提醒。|
|错误记忆实际送达并被Actor复述/据此行动|1|Circuit c74解析与初始化顺序颠倒。已确认一条强链，不等于全历史仅有一条。|

### 按问题本身区分，不先指定解决方案

- **信息真的不在后续输入里**：GA RStan输出合同、Circuit语法。需要和“信息仍在但没用好”分开。
- **从观察到结论时失真**：局部范围扩大、假设事实化、成功/失败反转、命令执行与目标完成混同。PMA与GA自身checkpoint都出现，但来源角色不同。
- **更新破坏了有效信息**：GAP过早删除、旧结论未失效、返工把较新事实换成旧片段。不能只统计新条目正确率。
- **消费时机/内容有问题**：正确记忆没及时用，提醒重复已知内容，或者把错误摘要直接送出。零提醒本身不是错误标签。
- **模型/运行工程问题**：JSON协议拒绝、审核解析失败、bridge TypeError、provider与Docker终止，单列而不当作整理失败。
- **任务本身仍需解题或操作判断**：算法未解、错误验收范围、破坏输入。现有材料不能证明记忆机制本应救回全部这些错误。

## 必须分开的证据层次

1. 任务Agent做错，和P1把它记错，是两件事。忠实记录一个错误想法不应被重新包装成已证实事实。
2. P1提出错误更新，不等于审核后写入。旧摘要中“原v4和r1最终均写Task complete”过强：原v4最终实际状态停Step30，Step32完成提议未提交；r1确有完成声明写入。tag组最终停Step10“Next:Add PATH”，原合成比较组停Step19“Remaining:Add PATH”。
3. 错误在库中，不等于已注入Task。SQLite多次0提醒只能证明PMA未纠偏，不能证明错误状态经提醒导致Actor失败。
4. 提醒送达后重复，不等于首次帮助。RStan Actor17早于首提醒自行发现行数问题；Circuit Actor83先发现格式问题，P2到86才提醒。
5. Circuit c74是已钉住的强传播链：P1倒置源码执行顺序，P2实际发送，Actor复述并采取相关修改。它不等于最终零分的唯一原因，相关修改本身也不一定有害。
6. 现有源码/日志能反驳某些摘要，但不能补出从未进行的验证；“尚未确认”不能写成“已证明失败”。

## 覆盖边界

主表每条按run_id去重。详细未评价尝试、未纳入来源及准备失败见RUN_LEDGER.json的pma相应字段。用户报告中没有公开的材料不假装已审计。本报告只使用各包白名单可见字段与评价摘要，未重新打包原轨迹，也不对全部来源包作新的脱敏完整性保证。本报告不包含隐藏测试正文、隐藏推理或私有配置。数字是描述性清点，不是配对实验或泛化估计。
