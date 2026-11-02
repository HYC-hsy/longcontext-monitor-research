# 真实轨迹追加审计：错误最先出现在哪里

2026-11-02。继续检查已经运行过的轨迹，未创建测试案例、运行模型或Task、修改方法。T表示任务Agent调用，C表示PMA周期；通常C(n+1)消费Tn，所以不能把同编号当同一时间。只读取白名单可见内容。

## 起源与后续行为

|真实运行|具体问题|最早可见错误来自谁|后续发生了什么|
|---|---|---|---|
|SQLite pma-740db27b2d4b4ee6|安装超时后删编译器GAP|P1 C5首先推断likely completed，Actor T4仅说正在安装|T5检查gcc/gcov仍不存在；C6更正状态但没恢复GAP；Actor自行重试。P2始终静默。|
|同一SQLite运行|提前写Task complete|P1 C12先写完成；Actor T11只说正在加PATH|T12裸sqlite3两次失败；C13仍保持完成。Actor T13尝试修复、T14才最终完成。P2有反证仍静默。|
|SQLite pma-87f5c8cf56124b29|同脚本PATH成功扩大为持久完成|P1 C16先写完成并删GAP；Actor T15只写脚本并在当前shell export|Actor T16后宣布完成。P2静默；原生0/3。在线没有修正后独立调用证据，不能倒灌后置评价。|
|SQLite pma-c818075eb46b4272（最终通过）|一次超时记成两次|P1 C9新增计数，T8其实只有checkpoint|真正第二次apt执行在T9且成功，C10才更新。错误未送达Actor。|
|RStan pma-0df5d41e7d4049c2|分键猜测变成已定位根因|P1 C22把Actor T21的条件调试升级为确定根因|过强断言在内部status；经验正文仍有check if。P2 C22静默。|
|同一RStan运行|从CSV一维推成fit本身一维|Actor T22 checkpoint先断言；P1 C23继承保存|T24实际debug为(3,1000)，Actor与状态纠正，但错误经历仍留库。未发现其被转达。|
|Circuit pma-4a1d5d3e5ed349e0|初始化/解析顺序写反|P1 C74先新增BEFORE parsing细节|P2 C74有源码反证仍发送；Actor T74复述，T75采取相关修改。确认传播，不证明最终零分由此唯一造成。|
|同一Circuit运行|32位要求缩成16位|Actor T42先缩范围，P1 C43/C44继承并称约束|相关P2静默，不能说范围缩减由PMA提醒触发。|
|同一Circuit运行|旧19,158 gates记录留库|Actor T79先说结构看似正确，P1 C80保存并未及时撤除|T136产物67,258 gates，T137 Actor自己知道超标；旧条目没被后续选中，不能说旧计数误导最终交付。|
|OCaml pma-628546435058411d|free双推进诊断|Actor T15先提出，P1 C16写成确定原因|修复未通过；后来P1 C41又新增错误源码归因，见下表。|
|同一OCaml运行|把统计语句误当live指针推进|P1 C41首先添加错误行号解释，C47强化|P1/P2输入都有参考函数中真正统一p+=wh语句，仍误读；这些错解释未送达Actor。|

**不能再笼统说“都是Actor先错，P1只是照抄”。也不能反过来说P1先错就造成Actor后续错误：多次运行P2没有实际提醒。**

## 旧版自由生成P2的额外问题

|运行|当时证据|P2做了什么|实际后续|
|---|---|---|---|
|原v4 SQLite pma-56b78b0c9cd546be，C7|早先缓存有33个包，随后glob找不到|断言是glob问题、包应该仍在，且错误声称早先命令没用glob|实际发送后Actor T7复述shell glob issue并做直接ls/find。新的目录输出只有lock/partial，P2后续继续猜目录/权限。|
|旧合成 SQLite pma-cad24bdee18740bf，C22|新调用sqlite3 --version明确command not found；旧调用仅当前shell成功|可见输出明确承认新子进程没source脚本，却仍认为任务成功、无需提醒|P2返回no_intervention。最终库仍保留PATH待办，不能把此次沉默都归咎于P1的完成状态。|

这里第二行并非“二阶段没看到失败”：其可见返回主动解释了失败，却把它排除在完成判断之外。第一行证明自由生成的二阶段也可能自己添加错误解释；合理的排查动作本身不等于有害，也不能据此归因最终零分。

## 之前尚不具体的失败，补查到了什么

|任务|进一步查明的事实|仍未知部分|
|---|---|---|
|OCaml GC|5次patch（T17/25/34/43/46）、4次修改后build；T18超时挂住，T27/35/47在bootstrap编译camlinternalFormatBasics.cmi时段错；basic测试未执行|没有证据确定一个唯一根因或正确修复。不能再写“六次修复均测试失败”。|
|GA HTML过滤|T1代码全局正则会删合法正文中的事件属性样式文本；字面javascript URL匹配未处理字符引用/空白规范化；默认文本IO不能保证CRLF保真；T2未自测即完成|静态发现实现缺陷，不是本轮实际运行了反例；不能对应原生两项失败各自是哪条。|
|GA SQL优化|实际仅前5行与offset100的5行匹配，后续比较超时；T9却写前105行匹配，T10扩大为整体一致|原/新SQL静态对照未发现明确语义错误，原生零分精确原因仍未知。不能把验证夸大直接冒充失败根因。|

## 原始公开来源与定位

1. SQLite精简运行/OCaml：归档[d9837cd](https://github.com/HYC-hsy/longcontext-monitor-research/raw/d9837cd221bb7ae2d1c90cdd0033d94dc328d2cc/pma_evidence_review/diagnostic_packages/PMA_P1_LEAN_SQLITE_OCAML_REAL_DIAGNOSTIC_20261101.zip)。SQLite成员runs/sqlite-with-gcov/host-events.jsonl L9/T4、L11/T5、L23/T11、L25/T12、L27/T13、L29/T14，及maintenance-cycles.jsonl C5/C6/C12–14。P2 C13/C14请求同时含PATH失败回执。OCaml对应runs/fix-ocaml-gc/，T17/25/34/43/46为patch，T18/27/35/47为build；C41/C47为源码解释。
2. 两阶段对齐SQLite：归档[aa482e89](https://github.com/HYC-hsy/longcontext-monitor-research/raw/aa482e89da0ded3a3e55da71b72d6bec08487136/pma_evidence_review/diagnostic_packages/PMA_ALIGNED_P1_P2_SQLITE_REAL_DIAGNOSTIC_20261101.zip)，visible/host-events.jsonl L31/T15、L33/T16；maintenance-cycles.jsonl C13–16。
3. 无审核SQLite成功运行：归档[1d7eb456](https://github.com/HYC-hsy/longcontext-monitor-research/raw/1d7eb456203ba86b904b206202c7987702f188ee/pma_evidence_review/diagnostic_packages/PMA_NO_REVIEW_SQLITE_REAL_DIAGNOSTIC_20261101.zip)，visible/host-events.jsonl L13/T6、L17/T8、L19/T9；maintenance-cycles.jsonl C9；PATH实际软链和直接命令成功见T14，不能因P1早于Actor写完成就判错。
4. RStan/Circuit：归档[2fd7f818](https://github.com/HYC-hsy/longcontext-monitor-research/raw/2fd7f818c659adb7d16918fe35c9fdc62ab77c7a/pma_evidence_review/diagnostic_packages/PMA_BANK_DISPLAY_RSTAN_CIRCUIT_REAL_DIAGNOSTIC_20261102.zip)。RStan task/research_events.jsonl L172/T21、L180/T22、L196/T24，pma/gap_cycle.jsonl C22–24。Circuit同名文件L334/T42、L587/T73、L593请求74、L596响应74、L604响应75、L636/T79、L1094/T136、L1102/T137；pma/gap_cycle.jsonl C43/44/74/80/152。
5. 原v4合成提醒：归档[221c3bd](https://github.com/HYC-hsy/longcontext-monitor-research/raw/221c3bd63d2ce569432a0d7911877dece028b809/pma_evidence_review/diagnostic_packages/PMA_V4_REVIEWER_R1_SQLITE_TWO_REAL_TASKS_20261031.zip)，baseline/memory/trajectory_memory.json steps7–9的context_for_action，baseline/task/research_events.jsonl L58/T7、L76/T9。
6. 旧合成提醒：归档[1f63a2c0](https://github.com/HYC-hsy/longcontext-monitor-research/raw/1f63a2c0f74fc41d3c6f91946d70da0008676d67/pma_evidence_review/diagnostic_packages/PMA_VERBATIM_SELECTION_SQLITE_TWO_REAL_TASKS_20261031.zip)，baseline/memory/trajectory_memory.json step22的raw_response_phase2、user_prompt_phase2及final_bank.json status。此处只使用可见返回，不使用reasoning字段。
7. GA SQL/HTML：归档[918bcb99](https://github.com/HYC-hsy/longcontext-monitor-research/raw/918bcb99d28a70997e73450168a6c00cb20e1c12/experiment_runner/ga20_evidence/GA20_FINAL_VISIBLE_20261030.zip)，04-query-optimize/task_turns.jsonl T7/8回执source59/67、T9响应70；13-filter-js-from-html/task_turns.jsonl T1写入source6、T2完成source14。HTML静态解释核对[WHATWG HTML属性解析](https://html.spec.whatwg.org/multipage/parsing.html#attribute-value-(double-quoted)-state)、[URL解析](https://url.spec.whatwg.org/#concept-basic-url-parser)、[Python文本换行](https://docs.python.org/3/library/functions.html#open)。

本补充不更新为“全部根因已定位”，也不把原统计的1条P1新增错误传播链改成两条同类型：新增发现是P2自身添加解释的另一种传播链。未把原始轨迹重新打包。
