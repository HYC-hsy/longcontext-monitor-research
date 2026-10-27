# Citation-only 开发样本集：本地发布审查稿

**Windows 离线预检修复及新的接收步骤：见 [WINDOWS_PREFLIGHT_HANDOFF.md](WINDOWS_PREFLIGHT_HANDOFF.md)。**
下文保留最初发布审查时的历史状态与方法边界；不得把旧版的离线通过记录当作 Windows 实机验收。

当前状态：仅本地构建及离线验收。没有 commit、push、上传、真实模型、Task、评价或正式记忆写入。
用户已确认仅benchmark/、新增测试及白名单ZIP范围；仍待父线程完成审查并明确开始发布。其它私有历史发布拒绝不变。未读额外私有日志/profile/private_client/凭据。

## 固定来源与恢复

生产审核器固定 a4aeb1fb940bda72df8558c1dc6b935019ae36d9；原生产代码、SYSTEM、projection、parser、CLI不改。
原始材料仅来自公开提交 72152913f545ca36a75b68e8796e24a6e24f9f81：
`method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/source_window_two_real_20261025/`
的根INDEX及两个slot的INDEX、memory_payload.jsonl.gz、trajectory_memory.json.gz、gap_cycle.jsonl.gz、memory.json.gz。
精确路径、文件字节和SHA256在candidate_data/inventory.json.files，共11个文件；逐文件与git固定commit字节比较，
随后复用原gzip/解压hash、manifest、revision及引用校验。构建只读指定文件，不扫描其它归档。

参考诊断仅只读：08f8c6187f2d322d799b0ca388c967eedd33e910 的
`pma_evidence_review/diagnostic_packages/PMA_AUDITOR_SUBMITTED_CITATION_REAL_DIAGNOSTIC_20261026.zip`。
70940字节，SHA256 da6785f44401a085b60eb6fe821cf278667653ab02d1a6327fa7aa74e8a9d0a7；已核对CRC并读DIAGNOSIS。
初次本地Git缺对象自动取回遇DNS失败，之后仅只读fetch成功。该ZIP不复制进拟发布文件。
其模型结果不是reference gold，标签基于已读原文逐项另作判断。

清点SQLite15周期36操作、HTML2周期10操作。SQLite C6–C13共17操作因公开prompt脱敏后不再匹配
原manifest而整周期排除。C6经历史revision联结 cycle_66ef7ceb5ab74c408687037e224a0c88：
公开prompt SHA fe2021cb8c50e2b24390d08c19e8e22a5ca515fc16787a6c75b2fd39b91d86c3，
manifest.request_sha256 cbdc0ff9fa7a34831c7526f5748d083e11e3cf7c7488319c9cb4355e4c3282e5。
第一个[REDACTED]起于Python字符12645（0基），共66个标记。其余周期诊断在inventory。
这是公开内容变化，不是仅靠样本名硬编码失败；未放宽校验，也未用这些周期整源构造控制。

其余29操作：ready15，no_evidence7，citation_set_not_eligible4，delete协议不适用3。
ready中9条选入历史主集，另外6条涉及计划/推论/范围争议，单列eligible_not_in_main，无主集标签。
准备不合格没有被伪标为insufficient。所有历史内容、原提交引文、revision均不改。

## 样本、标签与独立身份

29条：historical_original 9（supported2 / insufficient7 / contradicted0）；
trace_derived_control20（supported7 / insufficient6 / contradicted7）。总计9/13/7。
来源周期SQLite1、3、5、14、15及HTML1、2。引用角色计数：task_instruction6、tool_command15、
tool_observation18；重复使用同一源不算独立证据。没有memory_derived或agent_report覆盖。

specs.json保存逐条完整派生正文、字面选段规则及评估说明；candidate_data/cases.json保存所有完整
最终操作和引用、坐标/hash、origin commit/path/cycle/op/revision。正文不做抽取/拆分。
派生正文和引用集变化明确记为trace_derived_control，memory/revision使用内容和选段规则SHA生成
的benchmark身份，不带positive/negative等评估名称，不冒充真实第一阶段写入。

benchmark adapter只从已验证可见切片选精确唯一字面span。若保留完整源记录，沿用candidate校验；
若原source记录已不保留（例如只显示头尾的命令wrapper），不编造source全文hash，明确null及
unavailable_not_asserted，仍要求字面引用在已验证manifest可见切片内且唯一，记录snippet摘要。
这只适用于新的派生基准引用；没有关闭或更改历史citationpacket的严格准备规则。

core.build_case先取得生产requests，再仅以同一production projection替换目标及明确选择的引用材料。
SYSTEM、output example/schema、来源角色语义和normative空字符串保持原样。历史请求必须逐字相同。
公开core.run必须先加载外部固定摘要对应的数据集，再使用真实CapturedTransport、json_value和cr.parse，不复制宽松解析器，也没有extract/local模型。

标签是事后开发reference judgment，不是外部gold、盲评或模型效果。缺证不等于矛盾；反向控制限于
同一次工具报告/同一代码片段/同一任务规范。完整代码可推出窄静态性质，未执行其中代码；写入回执
只能支持写入报告，不能证明清除所有XSS。PATH正例联合命令及回执且限定export后的shell。

标签/reason/family/change仅在specs和evaluation-only侧，最终模型payload不含这些字段或sample_id。
离线fake统一返回insufficient，与reference标签无关。score的混淆矩阵是流程验收，不宣称模型准确率。
按原source_id核对一个源只属于一个family；相关源码/写入、跨周期PATH等共同归组。全部development，
两个任务不足以做泛化评估，不随机分拆改写成train/test。以后留出必须使用新的证据家族/任务并独立标注。

## 可复制离线验收

在仓库根目录，用现有Python与依赖；本次macOS Python3.11.15、既有regex，无安装或真实profile读取。
本机命令加 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:../offline-deps`，不执行轨迹命令。

```bash
python -m unittest discover -s pma_evidence_review/tests -v
python -m pma_evidence_review.benchmark build --repo . --out /new/dataset
python -m pma_evidence_review.benchmark validate --dataset /new/dataset --manifest-sha256 dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928
python -m pma_evidence_review.benchmark export --dataset /new/dataset --manifest-sha256 dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928 --out /new/export.json
python -m pma_evidence_review.benchmark fake --dataset /new/dataset --manifest-sha256 dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928 --out /new/fake
python -m pma_evidence_review.benchmark score --dataset /new/dataset --manifest-sha256 dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928 --results /new/fake/results.json --out /new/fake-score.json
```

所有输出路径必须不存在。本版冻结MANIFEST SHA256：`dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928`。
validate/export/fake/score均必须显式传入该审查摘要，不能现算待验manifest摘要当可信输入。
MANIFEST逐文件hash、schema/源码版本/文件集、每case输入hash均验证；从闭合材料重建完整生产
请求，精确比对SYSTEM、prompt、tools、phase、strategy、evidence_policy和output example，拒绝追加内容。
这不是外部签名：构建阶段固定Git源字节和可见性验证、加载阶段冻结产物检查、单case规范投影
检查是三层不同保证。若可信交接摘要本身被替换，不能靠同一目录自带哈希证明来源。
111项离线测试通过；OFFLINE_TESTS.txt保留完整stdout/stderr。29份export与fake接收payload一致。
生产文件与固定代码SHA逐字比较记录在PUBLICATION_REVIEW.json。Windows现有回归保留，未另跑Windows实机。
实施步骤：core初版约220行；样本specs独立440行；CLI及测试约130行；最后完整性/文档独立修订，
每一步代码增删不超过600行。生成样本及日志是工具输出，与人工代码/配置分列。未commit/push。

## 后续本机真实测试指令（本轮不执行；需新的真实调用授权）

先审查并冻结拟发布清单、代码与dataset manifest；若尚未批准发布则只使用本机冻结版本。
另获真实调用授权后，确认现有opus48配置和执行范围，不加人为预算或费用统计。验证完整离线套件。
使用下列真实入口（这里只提供命令，本轮没有执行）：

```bash
python -m pma_evidence_review.benchmark run-profile --dataset /absolute/dataset --manifest-sha256 dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928 --repo /absolute/checkout --profile /private/existing-profile.json --profile-key claude_monitor_opus48 --out /private/new-benchmark-run --execute-authorized-real-model
```

未传显式flag会在profile读取前拒绝。先验证外部固定manifest及全部文件hash，再构造既有客户端；
运行路径仅解析cases/requests，evaluation-only和inventory只核对文件字节hash，不解析成模型材料。
client只接收case.request里的system/prompt/tools。默认按冻结case顺序，各一次，不重试。
发生call_error/protocol_error/parse_failure时立即停止后续调用；后续所有项显式
not_run_after_engineering_error。每项追加并flush results.jsonl，最终保存完整results.json；
CLI工程失败后非零退出。raw/model_verdict保留；请求/响应捕获继续沿用生产CapturedTransport。
profile/private_client不入公开包。主进程被外部中断时至少已有flush的journal可诊断，不自动恢复重跑。

运行结束后单独评分（结果文件必须完整；被中断时先诊断，不伪造缺项）：

```bash
python -m pma_evidence_review.benchmark score --dataset /absolute/dataset --manifest-sha256 dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928 --results /private/new-benchmark-run/results.json --out /private/new-benchmark-score.json
```

每项结果绑定benchmark_input_sha256与audit_request_sha256，评分拒绝同sample_id但不同请求的结果。
分别输出historical_original与trace_derived_control的矩阵、有效样本、工程错误、未运行和缺项数；
same_conclusion_pairs逐端列出参考/实际判断、工程状态及matches_reference，不能判定时为null，
不是false。整体矩阵保留作辅助，不能用混合总分替代分层分析。原46操作准备库存独立报告。
不要把fake评分当真实结果。发现标签争议先标记移出主分析，不看模型答案后偷偷修改冻结标签。
目前仅公开来源的benchmark/、新增测试和白名单交付ZIP获得范围确认，执行发布仍待父线程明确开始；真实实验及真实结果发布仍需单独授权。

## 同结论换证据配对

新增d-write-same-conclusion-weak-evidence与d-regex-same-conclusion-weak-evidence；
正文分别与d-write-positive、d-regex-positive逐字相同，证据仅为原HTML源码成功字符串。
两项reference均insufficient，matched_pair仅在评估侧。原充分项及原27条case未改。
重复结论是有意的证据敏感性控制，不代表新增两个独立事实；与原项使用同一source family。

## 可运行交付补充验收

新增run-profile只在离线测试中mock load_profile_client，未打开真实profile。
测试覆盖缺flag禁止loader、实收payload、失败后不再调用、逐项journal与最终结果一致、原始异常文本，
以及两种身份摘要错配拒绝、分层计数、同结论配对参考对照。fake结果不代表方法效果。
