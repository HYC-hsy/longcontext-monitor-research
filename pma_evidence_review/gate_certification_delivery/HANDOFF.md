# Gate 生命周期认证接收指令（认证补丁候选）

父版本 `57b204aefeaf3768b47a698dabde3a7880a93f49`；以最终审查回复的修复 exact SHA 为准。
上一轮 Windows 隔离回归 282/282 通过，A 零模型夹具完成；gate-only 在 Task 启动前因缺失
runtime policy 被拦截，gate-one-repair 未启动。归档 `df7550644bba1598ff424c8c52b0dcf63737214a`
是部分诊断包；未收录的原始材料不等于没有产生，不能据此声称 gate 已认证。

本轮修复三处接线缺陷，不改模型提示、审核语义或历史结果：

1. gap 候选缺 policy 现在在 `single_run.prepare` 创建输出、读取 profile、假授权和启动运行之前报错；
   不自动补限额、不绕过 Harbor 最终策略校验。命令补上 B 专用 `--runtime-policy-file`。
2. gate 原先错误写入 stateful-fake 分支、实际 prepare 的 plan 却未保存，导致显式 gate 丢失。
   现在写到正确 plan，并在生成 manifest 后检查 gate 原值绑定，缺失/错模式不再发布 manifest/run identity。
   同时恢复无关 stateful-fake 准备路径，不增加 gate。
3. batch 预检 spec 同步传入冻结 gate 和已校验的 fake 标志，避免新 gate 在预检再次丢失或把首次假认证误作真实启动。

下述认证必须使用新固定源码、新目录、新 run_id：A、gate-only、gate-one-repair 各一次。
旧 A 虽成功，但源码身份已变化，不能直接套入新证书；本次不是在旧冻结运行上补参数重跑。
此前失败 run 的卷身份记录仍为 unknown，不能回填 clean；只读排查与新运行认证分别记录。
没有运行任何新 Harbor/Docker 生命周期、真实模型或正式 Task。本轮离线证据见 `policy_preflight_20261028/`。

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
# 使用既有解释器与独立 Harbor checkout，不是 PMA vendor Harbor。
$Python='<既有 Python3.12+ 可执行文件>'
$NativeHarborSource='<既有独立 Harbor 源码根目录>'
$Reports='<全新离线回归报告目录>'
# NativeHarborSource 必须为干净的 459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc。
& $Python -X utf8 -B -m pma_evidence_review.tests.run_gate_regressions --native-harbor-source-root $NativeHarborSource --report-dir $Reports
if ($LASTEXITCODE -ne 0) { throw 'Offline regressions failed; keep both child logs and stop' }
```

此 runner 禁止网络连接（Windows asyncio socketpair 例外），无 profile 读取，无真实模型。
协调进程不导入 PMA/Harbor；两个子进程都执行，即使前一个失败也保留后一个结果。
`pma.json`、`native.json` 记录完整测试清单和实际 module origin，`*.stdout.txt` /
`*.stderr.txt` 保留原始子进程输出，`summary.json` 聚合真实退出码、计数与重复清单检查。
PMA 必须来自当前 checkout 的 vendor；native 必须来自指定的干净固定源码，拒绝 vendor 回退。
省略 `--native-harbor-source-root` 时，只接受解释器既有安装所指向的同一固定干净源码；
不要用随便安装的同名 Harbor 或把 vendor 放进 native 路径来代替。
Python3.11 仍只有原先一次“整个 native 模块未执行”的明确 skip，不能算 native 验收；
Python3.12+ 不新增 skip。完整接收预期为 279 PMA + 16 native = 295，零失败/错误/跳过。
原 282 个测试全部保留且原文件字节不变，新增 13 个 policy/入口链回归；原先报错的 8 个边界测试不得删减或降级。
上次 Windows 的既有路径是 `E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe`
和 `E:\LongContext\bench_runtime\m4\harbor-src`，使用前仍须核对实际存在与固定身份。
云端通过不是 Windows 实机通过，也不是 Docker 生命周期或两种 gate 模式认证。

## 接收端零模型 Harbor 认证：完整命令

本节是后续独立认证步骤，不由 runner 修复通过自动授权执行。
必须具备既有 Docker/Harbor 环境和本地官方镜像；不下载新依赖来绕过失败。
先只读执行 `docker info --format '{{.ServerVersion}}'` 与 `docker info --format '{{.OSType}}'`，
退出非零、空版本或非 linux 立即停止本节。最近本机已读到 Linux Engine 29.6.1，但需重新核对，
不得只因历史可用或离线通过而跳过检查；本节不启动/安装 Docker、不生成真实授权。
官方源码固定 2fd12b88aafdd04a52c298e3940bcb189f9766d6；Harbor 固定
459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc。使用现有 secret-free fixture profiles，
不得把真实 key/profile 拷进交付目录。下面变量是占位符，换成已有本地路径；不是私有路径示例。
Task/PMA fixture profiles 仍需符合既有 Opus4.8配置形状；fixture只使用fake传输。
不要使用 --candidate-profile-fixture（该参数属于其它 PoS 路径）。

先从固定历史 Git 原件导出已采用的 requested policy，不手写新预算、不使用含派生字段的 resolved policy。
固定归档 `72152913f545ca36a75b68e8796e24a6e24f9f81` 的 SQLite/HTML IDENTITY.json 两者均记录：
`agent_timeout=uncapped, task_turns=uncapped, verifier_timeout=official`。仅复用该执行策略，不复用旧证书。
这个 uncapped 是已有显式实验策略，不是代码默认或因为失败而新放宽限制；Harbor verifier 仍取原任务官方时限。
若现有已批准策略与此不同、固定原件无法读取或无法确认沿用，停止并报告，不自行替换策略。

```powershell
$Repo=(Get-Location).Path
$RuntimePolicy=Join-Path $Reports 'approved_requested_runtime_policy.json'
# 若固定对象本机不存在，只抓取该固定归档，不切换/覆盖当前源码。
git cat-file -e '72152913f545ca36a75b68e8796e24a6e24f9f81^{commit}'
if ($LASTEXITCODE -ne 0) {
  git fetch origin 72152913f545ca36a75b68e8796e24a6e24f9f81
  if ($LASTEXITCODE -ne 0) { throw 'Cannot fetch fixed policy provenance; stop' }
}
@'
import hashlib, json, pathlib, subprocess, sys
repo, output = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
commit = '72152913f545ca36a75b68e8796e24a6e24f9f81'
prefix = 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/source_window_two_real_20261025'
rows = []
for task in ('01-sqlite-with-gcov-r1', '02-filter-js-from-html-r1'):
    path = prefix + '/' + task + '/IDENTITY.json'
    raw = subprocess.check_output(['git', '-c', 'core.longpaths=true', 'show', commit + ':' + path], cwd=repo)
    requested = json.loads(raw)['runtime_policy']['requested']
    rows.append({'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'requested': requested})
expected = {'agent_timeout': 'uncapped', 'task_turns': 'uncapped', 'verifier_timeout': 'official'}
if any(row['requested'] != expected for row in rows):
    raise RuntimeError('Fixed historical policies differ; do not invent a replacement')
raw = (json.dumps(rows[0]['requested'], sort_keys=True, indent=2) + '\n').encode('utf-8')
with output.open('xb') as f:
    f.write(raw)
record = {'source_commit': commit, 'sources': rows, 'requested_policy_sha256': hashlib.sha256(raw).hexdigest()}
with output.with_suffix('.provenance.json').open('x', encoding='utf-8', newline='\n') as f:
    json.dump(record, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps(record, ensure_ascii=False))
'@ | & $Python -X utf8 -B - $Repo $RuntimePolicy
if ($LASTEXITCODE -ne 0) { throw 'Approved policy source/export failed; stop before fixtures' }
```

A/U 不接收 runtime policy 覆盖，因此不得把此参数加到 A/B 共用的 `$Common` 中。
B 两种模式和其后两份 real prepare 必须显式传相同 `$RuntimePolicy`；不得改 frozen manifest 补字段。

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
& $Python -X utf8 -B -m "$Prefix.single_run_fixture" @Common --condition A --research-candidate U --output "$FixtureRoot/A"
if ($LASTEXITCODE -ne 0) { throw 'A native fake fixture failed; stop' }
foreach ($Mode in @('gate-only','gate-one-repair')) {
  & $Python -X utf8 -B -m "$Prefix.single_run_fixture" @Common --condition B --research-candidate pma_gap_evidence_v1 --citation-review-gate $Mode --runtime-policy-file $RuntimePolicy --output "$FixtureRoot/$Mode"
  if ($LASTEXITCODE -ne 0) { throw "$Mode native fake fixture failed; stop" }
  & $Python -X utf8 -B -m "$Prefix.collect_single_run_fixture" --a "$FixtureRoot/A" --b "$FixtureRoot/$Mode" --output "$CertRoot/$Mode" --task-profile-file $FakeTask --pma-profile-file $FakePma --research-candidate pma_gap_evidence_v1 --citation-review-gate $Mode
  if ($LASTEXITCODE -ne 0) { throw "$Mode collect/validate failed; stop" }
}
```

每个 B 运行后须核对实际冻结 plan 有 citation_review_gate，manifest.config 有同模式及
citation_gate_source_sha256、runtime_policy.requested；execution_identity.gate_config 与 manifest.config
完全一致，且 runtime_policy_effective.json 表明 Harbor 实际应用同一策略。最终仍以完整证书验证为准，
仅看到 CLI 参数、execution_identity 顶层 gate_config 键或阶段名称，不算 gate 已生效。

collect 只复制原脚本白名单、脱敏后再验证，哈希材料若脱敏破坏身份则拒绝。
新证书不靠人工填phase；由实际capture生成。缺第二维护/回执、没有repair等均失败。
先检查两个证书目录、FILE_HASHES、secret-free内容与原件，
仅将审核过的这两个目录提交本地 Git（正式验证继承原证据必须committed约束）：

```powershell
git add -f -- pma_evidence_review/gate_certification_evidence_local/gate-only pma_evidence_review/gate_certification_evidence_local/gate-one-repair
git diff --cached --stat
# 检查暂存内容仅为上述合成认证材料后再提交。不要git add整仓。
git commit -m 'Record reviewed synthetic native gate lifecycle evidence'
if ($LASTEXITCODE -ne 0) { throw 'Evidence must be committed before formal verification' }
foreach ($Mode in @('gate-only','gate-one-repair')) {
  & $Python -X utf8 -B -m "$Prefix.gate_certification" --evidence "$CertRoot/$Mode" --mode $Mode
  if ($LASTEXITCODE -ne 0) { throw "$Mode committed verification failed; stop" }
}
```

这里是本地证据提交，不授权上传 profile、private_client 或凭据；后续仅按最终交付指令的诊断白名单上传。若fixture失败，保存原错误报告，不自动重跑、不调低验证条件。
无Docker、镜像、Harbor、配置不符时停止此阶段；离线unit通过仍然不能启动真实实验。

## 认证通过后只准备配置；真实执行仍另行授权

以下 prepare 不发送模型请求，只读取用户已批准的既有配置；本实现线程没有执行。
不得复制/上传私有 profile 或凭据。仅准备并返回两份 manifest、config hash、run_id，不能生成真实授权或启动 run。
使用各模式对应证书，保持相同任务和其它设置，两个全新输出目录。

```powershell
$TaskProfile='<用户批准的既有Task配置.py>'
$PmaProfile='<用户批准的既有PMA配置.json>'
$Task='<用户批准的Task标识>'
& $Python -X utf8 -B -m "$Prefix.single_run" prepare --task $Task --condition B --research-candidate pma_gap_evidence_v1 --citation-review-gate gate-only --runtime-policy-file $RuntimePolicy --occurrence 1 --output '<全新gate-only准备目录>' --official-source-git $Official --task-profile-file $TaskProfile --pma-profile-file $PmaProfile --certification-dir "$CertRoot/gate-only" --native-context-policy required --research-capture-policy required
if ($LASTEXITCODE -ne 0) { throw 'gate-only prepare failed' }
& $Python -X utf8 -B -m "$Prefix.single_run" prepare --task $Task --condition B --research-candidate pma_gap_evidence_v1 --citation-review-gate gate-one-repair --runtime-policy-file $RuntimePolicy --occurrence 1 --output '<全新gate-one-repair准备目录>' --official-source-git $Official --task-profile-file $TaskProfile --pma-profile-file $PmaProfile --certification-dir "$CertRoot/gate-one-repair" --native-context-policy required --research-capture-policy required
if ($LASTEXITCODE -ne 0) { throw 'gate-one-repair prepare failed' }
```

原single_run run仍要求独立一次授权及manifest/run binding，未在此添加真实执行授权。
比较漏放、误拒、陈旧记忆、gap积压与Task效果，不以supported率作为质量。
没有新语义样本、真实模型结果或效果提升结论。

## Windows 字节保护补丁

collector 在每个输出认证根（例如 gate-only/、gate-one-repair/）生成 `.gitattributes`，
内容为 `* -text`；只作用于该目录及后代，并把属性文件纳入 FILE_HASHES.json。
上面的 `git add -f -- <两个证据目录>` 必须包含此隐藏文件；不要只挑JSON提交。
不得通过换行归一化重算原件哈希；不改变全局 core.autocrlf。
回归使用真实临时Git仓库，core.autocrlf=true下add/commit再新clone检出，
验证CRLF原日志、UTF-8证书、索引及属性文件字节与Git blob完全一致，目录外属性不变。
793a及其原日志保留；接收方须从最终含字节保护补丁的SHA重新生成认证材料。


## 完整诊断包一次性交付

每个运行命令执行后核对退出码；任一阶段失败立即停止后续模式，不现场改源码、改响应或自动重跑。
保存原输出及未执行清单。旧 df7550644bba1598ff424c8c52b0dcf63737214a 包及旧 unknown 清理记录保持不变。
成功或提前停止，都按本轮实际发生材料制作一个新 ZIP 与外部索引，建议新名称
`PMA_CITATION_GATE_POLICY_BINDING_ACCEPTANCE_20261028.zip`（实际日期变动时同步改名，不覆盖旧包）。

白名单包括：固定源码/环境/来源身份；两个隔离子进程原始输出、测试清单和 summary；
固定历史 policy 导出及来源哈希；Docker 只读结果；实际 A/B 夹具命令、原始日志、计划和 manifest、
execution_identity、runtime_policy_effective、worker 捕获、memory/gap/receipt 与最终 bank、
native 合成生命周期和证书核验材料；授权撤除与限定 run_id 的容器/卷清理报告；
两份 prepare 的可公开计划/身份或未产生说明；诊断说明及逐文件哈希索引。
原始 fixture 本机目录应保留，不能用 collector 的脱敏副本代替原始请求/回执而声称原件完整。
仅将白名单真实产生的文件纳入；逐项区分“未产生”“已产生但未收录”“已收录”，不要把缺件统称未执行。

禁止上传 profile、private_client、凭据、授权原件、秘密端点或无关个人材料。
如必需原件含秘密或白名单无法安全完整发布，停止公开上传并说明缺项，不静默改写/脱敏后宣称原始完整。
按已授权目的只提交该 ZIP 及外部索引到
`HYC-hsy/longcontext-monitor-research/pma_evidence_review/diagnostic_packages/`；
使用新归档提交、非强制推送，不上传整个工作区。
推送后重新 fetch，读取远端 exact commit 的 ZIP 字节，核对大小、SHA-256、CRC、逐文件哈希及外部索引。
返回代码 SHA、实际证据提交 HEAD、归档 SHA、下载链接、各阶段真实执行/停止状态和剩余限制。
工程回归、零模型生命周期与模型/Task 效果分别报告；本轮不运行 29 条审核集，也不调用真实模型或正式 Task。
