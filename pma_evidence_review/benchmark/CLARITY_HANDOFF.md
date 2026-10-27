# Citation-only 一般性语义与来源角色澄清候选

候选已本地实现，发布前需父线程审阅；此交接不授权当前线程真实运行。
基线：ae31a01fb94535d7fb11bbd8b7adfdb639bdb446。
新入口：python -m pma_evidence_review.benchmark.experiment。
A策略baseline-a（默认）；B策略semantic-paraphrase-role-clarity-v1（必须显式选择）。
现有benchmark CLI、core、生产citation审核器、29样本、引文、reference标签及原manifest均未修改。
Windows POSIX仓库路径、Git单次core.longpaths=true、LF及既有socketpair修复保留。

## 最小变更及身份

experiment.plan先调用原load_dataset验证外部固定manifest，再生成策略计划。A的每条request与
原冻结request逐字一致；B只在SYSTEM的单一输出契约之前插入CLARIFICATION，并改review_strategy，
重算实际system/prompt/tools摘要。prompt、tools、content_sha256及全部可见材料不变。
B没有新例子、参考答案、分类器、拆分、外部检索或另一个模型。候选完整SYSTEM另存
CLARITY_CANDIDATE_SYSTEM.txt；这是给审阅者的提示文本，不含任何样本材料。

每计划记录strategy、父benchmark输入hash、父A请求hash、实际请求、experiment_plan_sha256。
运行器显式把已验证A请求映射到计划请求，再复用原core.run的顺序、严格解析、原raw保留及停止规则。
映射必须精确匹配原请求；只有实际计划请求进入CapturedTransport。每条结果（包括未运行项）
立即追加实际请求hash、父A请求hash、策略及计划hash，再持久化，不把B结果冒充A。
评分先逐项验证实验身份，才将父hash投影给原分层/配对评分器；拒绝错误策略、混用及旧无策略结果。
原benchmark_input_sha256仍是父样本身份，不冒充新的B请求身份。冻结数据哈希不是签名。

固定manifest：dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928
A计划：a1282f49e8538a991419eafcc2e7ca49704c15fbc1363c57cbb496317ec5b3f1
B计划：eb19addffa4401228fb4cf7aa6b0d24ea9a3b088441cfeffab62b004a3bc719e

## 开发线程接收与离线验收（PowerShell）

用发布最终回复提供的exact代码SHA替换$Code；新目录不得存在，不reset既有工作树。
使用当前Python及既有依赖，不为换环境重装。清理跨版本PYTHONPATH，保留本机必要环境配置。

```powershell
$Code = 'REPLACE_WITH_EXACT_CODE_SHA_FROM_FINAL_HANDOFF'
$Work = 'C:\pma-clarity-checkout'
git -c core.longpaths=true fetch origin research/pma-citation-semantic-clarity-v1-20261027
git -c core.longpaths=true worktree add --detach $Work $Code
Set-Location $Work
$env:PYTHONPATH = $null
$env:PYTHONUTF8 = '1'
$Data = Join-Path $Work 'pma_evidence_review/benchmark/candidate_data'
$Pin = 'dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928'
$Out = 'C:\pma-clarity-new-experiment'
New-Item -ItemType Directory -Path $Out -ErrorAction Stop | Out-Null
python -m unittest discover -s pma_evidence_review/tests -v
if ($LASTEXITCODE -ne 0) { throw 'Offline tests failed' }
python -m pma_evidence_review.benchmark validate --dataset $Data --manifest-sha256 $Pin
if ($LASTEXITCODE -ne 0) { throw 'Frozen dataset validation failed' }
python -m pma_evidence_review.benchmark.experiment export --dataset $Data --manifest-sha256 $Pin --strategy baseline-a --out "$Out\A-plan.json"
if ($LASTEXITCODE -ne 0) { throw 'A export failed' }
python -m pma_evidence_review.benchmark.experiment export --dataset $Data --manifest-sha256 $Pin --strategy semantic-paraphrase-role-clarity-v1 --out "$Out\B-plan.json"
if ($LASTEXITCODE -ne 0) { throw 'B export failed' }
python -m pma_evidence_review.benchmark.experiment fake --dataset $Data --manifest-sha256 $Pin --strategy semantic-paraphrase-role-clarity-v1 --out "$Out\fake-B"
if ($LASTEXITCODE -ne 0) { throw 'Fake wiring failed' }
```

检查两个plan摘要与上述固定值、A请求与dataset/requests.json一致、B仅改变澄清SYSTEM和策略/摘要。
原始测试日志CLARITY_OFFLINE_TESTS.txt：macOS Python3.11.15，120通过；没有新的Windows实机执行。
相关测试覆盖原115回归，另5项A/B请求隔离、标签不泄漏、实际payload、评分错策略拒绝、停止与raw、
CLI及profile loader替身。fake不证明优化有效。

## 后续真实A/B（必须另获执行授权，本次未执行）

两边使用同一固定checkout与manifest、现有opus48 profile和客户端参数、冻结29条顺序。
先完整A，再完整B，各条一次；不同Python进程。除了候选SYSTEM/标识，其余不变。
过去29条真实结果只能历史参照，不能替代此次同条件A。此候选已看过这些开发样本，不是留出验证。
工程错误即停，不自动修响应/重跑；语义verdict不同于reference不停止。
不加入成本/时延统计或人为预算。以下替换为已有私有profile路径，不能打印或复制其内容。

```powershell
$Profile = 'C:\private\existing-profile.json'
python -m pma_evidence_review.benchmark.experiment run-profile --dataset $Data --manifest-sha256 $Pin --strategy baseline-a --repo $Work --profile $Profile --profile-key claude_monitor_opus48 --out "$Out\real-A" --execute-authorized-real-model
if ($LASTEXITCODE -ne 0) { throw 'A engineering failure: stop, inspect saved artifacts; do not start B' }
python -m pma_evidence_review.benchmark.experiment score --dataset $Data --manifest-sha256 $Pin --strategy baseline-a --results "$Out\real-A\results.json" --out "$Out\A-score.json"
if ($LASTEXITCODE -ne 0) { throw 'A identity/score failure: stop before B' }
python -m pma_evidence_review.benchmark.experiment run-profile --dataset $Data --manifest-sha256 $Pin --strategy semantic-paraphrase-role-clarity-v1 --repo $Work --profile $Profile --profile-key claude_monitor_opus48 --out "$Out\real-B" --execute-authorized-real-model
if ($LASTEXITCODE -ne 0) { throw 'B engineering failure: stop; no retry' }
python -m pma_evidence_review.benchmark.experiment score --dataset $Data --manifest-sha256 $Pin --strategy semantic-paraphrase-role-clarity-v1 --results "$Out\real-B\results.json" --out "$Out\B-score.json"
if ($LASTEXITCODE -ne 0) { throw 'B identity/score failure' }
```

逐样本对照A/B原文、实际引用、verdict与explanation：分别检查改写等价性的误拒、扩大范围的误放、
解释是否把命令/源码写成已执行。保持reference冻结，争议另列不追改标签。保留历史/派生两层矩阵、
两组同结论换证据的两端结果；不能只用supported比例或29条匹配率声称泛化/优化成功。

完成后接收线程一次性归档公开诊断ZIP，使用新文件名和独立归档提交，不覆盖旧包。
只按白名单收集：固定代码/环境身份（无秘密）、原dataset manifest与公开case/评估文件、A/B计划、
各运行的experiment-plan.json、requests.jsonl、responses.jsonl、results.json/jsonl、分层评分、
逐项诊断、命令及离线测试stdout/stderr、逐文件字节/SHA256索引。不得递归打包$Out，
不得加入profile、private_client、凭据、HTTP头或无关个人文件。检查意外秘密，发现则停止发布并报告。
ZIP重开验证CRC与逐文件哈希，记录大小/hash/文件数；非强制上传同仓库新归档提交并回读远端字节。
给出exact SHA与固定链接；不能把本机路径当附件。当前线程仅准备这些指令，不执行真实实验。
