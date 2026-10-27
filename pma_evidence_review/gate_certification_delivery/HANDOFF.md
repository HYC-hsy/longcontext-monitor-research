# Gate 生命周期认证接收指令（认证补丁候选）

父版本 a51350908ed89fe511343770b9755d49e40059a9。以最终审查回复的补丁 exact SHA 为准。
本轮只实现和离线测试；本机没有 docker 命令，没有执行 Harbor 容器生命周期。
原生test_evaluation_bootstrap模块依赖Python3.12语法；本机3.11导入失败原文另存，最终runner明确skip该模块。接收方Python3.12将实际执行，不能忽略失败。
不得把 worker fake 通过当作完成 Harbor 认证。旧 gate_delivery 日志保持原件。

## 契约与变更

仍串行；不增加模型角色，不改固定单句审核提示。未来并发需单独设计：只读请求可并发，
同目标操作必须有序；当前全局 generation 不能简单 gather 多个 draft 后发布。

新增 gate_certification.py，证书是 B/gate_certificate.json。它不是签名或真实性保证：
每次核验重新读取 committed 原件并重算。原 native Harbor A/B 生命周期验证仍完整执行。
默认 baseline 严格只允许 maintenance/selection，旧证书不能证明 gate。
显式 gate 除原 native 验证外要求：

- execution identity 的 mode/共享源码/认证源码与当前 Git 字节相同；配置不得偷换。
- 真实捕获的请求与回执 call_sequence 一致，按周期 maintenance→逐操作review/repair→selection。
- 原请求 hash、可见 registry 与实际维护正文一致，逐引用复用 ci.prepare 严格绑定。
- 每次审核 payload 从闭合引用投影重新构造，与实际发送、保存的 raw 响应匹配。
- 修订保持 action/target、原维护材料；replace/withdraw 与第二候选、原引用一致。
- supported 才发布；最终 bank 使用原 canonical loader 验证；拒绝 revision 不在 bank。
- 下一 maintenance 必须实际携带完整冻结 receipt 并取得响应；只在日志写 delivered 不够。
- receipt/reviewer 控制文本不在来源 registry/selection。fixture 要有通过和拒绝；修订模式实际修订。

这套认证是固定合成生命周期测试，不是任意历史轨迹诊断器，遇到覆盖不足就失败，不能改证据迎合。
所有 receipt 条目新增 target_memory_id：既有目标保留 ID、status 为 status、新建为 null。
无效维护上下文先重置本轮报告，记录 maintenance_context_invalid；旧提交不重复计数，旧回执仍pending。
新增 frozen_visibility 仅在宿主诊断中，不进入审核模型。

## 本机先验收

在最终版本 checkout 根、既有依赖齐全的 Python 环境：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:LITELLM_LOCAL_MODEL_COST_MAP='True'
python -m pma_evidence_review.tests.run_gate_regressions
if ($LASTEXITCODE -ne 0) { throw 'Offline regressions failed' }
```

此 runner 禁止网络连接（Windows asyncio socketpair 例外），无 profile 读取，无真实模型。
Python3.11/源码 Harbor 导入适配只用于测试，不冒称修改生产 vendor 或验证 Windows 实机。

## 接收端零模型 Harbor 认证：完整命令

必须具备既有 Docker/Harbor 环境和本地官方镜像；不下载新依赖来绕过失败。
官方源码固定 2fd12b88aafdd04a52c298e3940bcb189f9766d6；Harbor 固定
459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc。使用现有 secret-free fixture profiles，
不得把真实 key/profile 拷进交付目录。下面变量是占位符，换成已有本地路径；不是私有路径示例。
Task/PMA fixture profiles 仍需符合既有 Opus4.8配置形状；fixture只使用fake传输。
不要使用 --candidate-profile-fixture（该参数属于其它 PoS 路径）。

```powershell
$Prefix='method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013'
$Repo=(Get-Location).Path
$Official='<本地官方源码Git目录>'
$HarborSource='<固定Harbor源码目录>'
$Runtime='<既有runtime目录>'
$Bench='<既有bench目录>'
$WorkerPython='<既有worker Python可执行文件>'
$HarborPython='<既有Harbor Python可执行文件>'
$FakeTask='<已有无秘密的Task fixture配置.py>'
$FakePma='<已有无秘密的PMA fixture配置.json>'
$FixtureRoot='<全新私有零模型fixture输出根目录>'
$CertRoot=Join-Path $Repo 'pma_evidence_review/gate_certification_evidence_local'
$Common=@('--task','sqlite-with-gcov','--official-source-git',$Official,
  '--task-profile-file',$FakeTask,'--pma-profile-file',$FakePma,
  '--ga-source',(Join-Path $Repo 'GenericAgent-main'),'--runtime-root',$Runtime,
  '--worker-python',$WorkerPython,'--harbor-python',$HarborPython,
  '--bench-root',$Bench,'--harbor-source-root',$HarborSource,
  '--python-home','cpython-3.12.12-linux-x86_64-gnu','--service-fixture',
  '--native-context-policy','required','--research-capture-policy','required')

# A也用当前源码重新做native生命周期，不能拿旧源码证书替代。
python -m "$Prefix.single_run_fixture" @Common --condition A --research-candidate U --output "$FixtureRoot/A"
if ($LASTEXITCODE -ne 0) { throw 'A native fake fixture failed; stop' }
foreach ($Mode in @('gate-only','gate-one-repair')) {
  python -m "$Prefix.single_run_fixture" @Common --condition B --research-candidate pma_gap_evidence_v1 --citation-review-gate $Mode --output "$FixtureRoot/$Mode"
  if ($LASTEXITCODE -ne 0) { throw "$Mode native fake fixture failed; stop" }
  python -m "$Prefix.collect_single_run_fixture" --a "$FixtureRoot/A" --b "$FixtureRoot/$Mode" --output "$CertRoot/$Mode" --task-profile-file $FakeTask --pma-profile-file $FakePma --research-candidate pma_gap_evidence_v1 --citation-review-gate $Mode
  if ($LASTEXITCODE -ne 0) { throw "$Mode collect/validate failed; stop" }
}
```

collect 只复制原脚本白名单、脱敏后再验证，哈希材料若脱敏破坏身份则拒绝。
新证书不靠人工填phase；由实际capture生成。缺第二维护/回执、没有repair等均失败。
成功也不自动发布采集材料。先检查两个证书目录、FILE_HASHES、secret-free内容与原件，
仅将审核过的这两个目录提交本地 Git（正式验证继承原证据必须committed约束）：

```powershell
git add -f -- pma_evidence_review/gate_certification_evidence_local/gate-only pma_evidence_review/gate_certification_evidence_local/gate-one-repair
git diff --cached --stat
# 检查暂存内容仅为上述合成认证材料后再提交。不要git add整仓。
git commit -m 'Record reviewed synthetic native gate lifecycle evidence'
if ($LASTEXITCODE -ne 0) { throw 'Evidence must be committed before formal verification' }
foreach ($Mode in @('gate-only','gate-one-repair')) {
  python -m "$Prefix.gate_certification" --evidence "$CertRoot/$Mode" --mode $Mode
  if ($LASTEXITCODE -ne 0) { throw "$Mode committed verification failed; stop" }
}
```

这里是本地证据提交，不授权上传真实私有包或凭据。若fixture失败，保存原错误报告，不自动重跑、不调低验证条件。
无Docker、镜像、Harbor、配置不符时停止此阶段；离线unit通过仍然不能启动真实实验。

## 认证通过且另外获得真实实验授权后才准备

以下prepare不发送模型请求，但读取用户既有配置；本实现线程没有执行。
使用各模式对应证书，保持相同任务和其它设置，两个全新输出目录。

```powershell
$TaskProfile='<用户批准的既有Task配置.py>'
$PmaProfile='<用户批准的既有PMA配置.json>'
$Task='<用户批准的Task标识>'
python -m "$Prefix.single_run" prepare --task $Task --condition B --research-candidate pma_gap_evidence_v1 --citation-review-gate gate-only --occurrence 1 --output '<全新gate-only准备目录>' --official-source-git $Official --task-profile-file $TaskProfile --pma-profile-file $PmaProfile --certification-dir "$CertRoot/gate-only" --native-context-policy required --research-capture-policy required
if ($LASTEXITCODE -ne 0) { throw 'gate-only prepare failed' }
python -m "$Prefix.single_run" prepare --task $Task --condition B --research-candidate pma_gap_evidence_v1 --citation-review-gate gate-one-repair --occurrence 1 --output '<全新gate-one-repair准备目录>' --official-source-git $Official --task-profile-file $TaskProfile --pma-profile-file $PmaProfile --certification-dir "$CertRoot/gate-one-repair" --native-context-policy required --research-capture-policy required
if ($LASTEXITCODE -ne 0) { throw 'gate-one-repair prepare failed' }
```

原single_run run仍要求独立一次授权及manifest/run binding，未在此添加真实执行授权。
比较漏放、误拒、陈旧记忆、gap积压与Task效果，不以supported率作为质量。
没有新语义样本、真实模型结果或效果提升结论。
