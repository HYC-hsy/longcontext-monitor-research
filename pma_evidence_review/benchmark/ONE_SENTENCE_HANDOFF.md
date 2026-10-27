# 单句候选：本地审查交接

本轮只比较 baseline-a 与 semantic-support-one-sentence-v1，不运行旧长段候选。
父版本 9d3d497e3730f78846ba6f23b9eec2d06fd88570。发布前等待审阅，暂无新发布 SHA。
新分支 research/pma-citation-one-sentence-v1-20261027。

唯一新增模型可见文本（紧邻原 SYSTEM 的 SUPPORTED means 判据之前，单独一行）：

> Assess support by meaning rather than wording, without broadening scope, dropping conditions, or strengthening the claims supported by the evidence.

新策略直接复制冻结 A 请求，再插入这一句；不叠加旧长段。
prompt/tools/输出示例/字段/样本/引用/标签/解析保持不变。
默认 A 与旧长段候选的请求及计划身份保持不变；新策略复用原 export/run/score、
实际请求/父请求身份校验、工程错误停止和响应保存。没有新框架或语义样本。

冻结 manifest：dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928

- baseline-a: `a1282f49e8538a991419eafcc2e7ca49704c15fbc1363c57cbb496317ec5b3f1`
- semantic-paraphrase-role-clarity-v1: `eb19addffa4401228fb4cf7aa6b0d24ea9a3b088441cfeffab62b004a3bc719e`
- semantic-support-one-sentence-v1: `ffb2999ed6f2da818ca554157b98974e230ed8977687ed12ac6a6abe25503451`


## 接收与离线检查

发布后以最终 exact SHA 建独立 worktree；使用当前 Python 和依赖，不重装。
在该 checkout 的根目录使用 PowerShell：

```powershell
$Data = 'pma_evidence_review/benchmark/candidate_data'
$Pin = 'dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928'
$Out = 'C:\pma-one-sentence-new'
New-Item -ItemType Directory -Path $Out -ErrorAction Stop | Out-Null
python -m unittest discover -s pma_evidence_review/tests -v
if ($LASTEXITCODE -ne 0) { throw 'Offline tests failed' }
foreach ($Strategy in @('baseline-a','semantic-support-one-sentence-v1')) {
  python -m pma_evidence_review.benchmark.experiment export --dataset $Data --manifest-sha256 $Pin --strategy $Strategy --out "$Out\$Strategy-plan.json"
  if ($LASTEXITCODE -ne 0) { throw 'Export failed' }
  python -m pma_evidence_review.benchmark.experiment fake --dataset $Data --manifest-sha256 $Pin --strategy $Strategy --out "$Out\$Strategy-fake"
  if ($LASTEXITCODE -ne 0) { throw 'Fake failed' }
}
```

核对上列计划摘要；去掉新句及其换行后，SYSTEM逐字等于A。其他模型payload字段相同。
原Windows路径/LF/longpaths回归保留，本轮实际环境是macOS arm64 Python3.11.15。
122测试通过仅证明工程流程，不证明语义改善。29条已参与调优，仅开发回归。

## 未来真实对照（此轮不执行；需接收线程获得真实执行授权）

使用同一候选提交、既有opus48 profile、相同冻结29条顺序。两个新结果，A29后新候选29，
各条一次；不复用历史A，不运行旧长段。无自动重跑，工程错误停，语义错误不停。

```powershell
$Work = (Get-Location).Path
$Profile = 'C:\private\existing-profile.json'
foreach ($Strategy in @('baseline-a','semantic-support-one-sentence-v1')) {
  python -m pma_evidence_review.benchmark.experiment run-profile --dataset $Data --manifest-sha256 $Pin --strategy $Strategy --repo $Work --profile $Profile --profile-key claude_monitor_opus48 --out "$Out\$Strategy-real" --execute-authorized-real-model
  if ($LASTEXITCODE -ne 0) { throw 'Engineering failure: stop all later runs; no retry' }
  python -m pma_evidence_review.benchmark.experiment score --dataset $Data --manifest-sha256 $Pin --strategy $Strategy --results "$Out\$Strategy-real\results.json" --out "$Out\$Strategy-score.json"
  if ($LASTEXITCODE -ne 0) { throw 'Identity or score failure: stop' }
}
```

诊断保留每项原响应和角色解释、分层/配对评分，不以supported比例宣称准确率。
未来结果包按CLARITY_HANDOFF的白名单一次性归档、独立提交，不覆盖历史ZIP；
不得包含profile/private_client/凭据或无关私有材料。当前只交付本地代码与离线记录，未发布。
