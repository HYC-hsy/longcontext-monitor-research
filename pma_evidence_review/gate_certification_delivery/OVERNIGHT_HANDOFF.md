# Gate 夜间接收、真实运行与完整交付指令

父版本 `6c85bc073fa382f1aac7326d1f0bf2e756fcd299`；以最终审查回复的修复 exact SHA 为准。
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

本节是本轮真实运行的必要前置认证；用户本次已授权继续，但离线通过不能替代原生夹具。
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
B 两种模式和其后四槽 real prepare 必须显式传相同 `$RuntimePolicy`；不得改 frozen manifest 补字段。

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

这里是本地证据提交，不授权上传 profile、private_client 或凭据；后续仅按最终交付指令的诊断白名单上传。若 fixture 失败，保存原错误报告，按本轮有界工程修复规则处理，不调低验证条件。
无Docker、镜像、Harbor、配置不符时停止此阶段；离线unit通过仍然不能启动真实实验。

## 本轮已授权的真实运行与恢复边界

本轮已授权以下四个真实槽位及下述有限工程修复；完成认证后可直接执行。
本节取代此前“只 prepare，真实运行需另行确认”的限制。授权只覆盖下面四个固定槽位，不是任意追加实验。
不要再等待一次机械性的启动确认；前置认证通过后执行。禁止调用 profile 以外的新服务、改模型或扩大任务数量。

固定顺序，全部 condition B / research_candidate pma_gap_evidence_v1：

1. sqlite-with-gcov × gate-only
2. sqlite-with-gcov × gate-one-repair
3. filter-js-from-html × gate-only
4. filter-js-from-html × gate-one-repair

两种模式均使用固定单句审核策略，任务与 PMA 都用用户既有 Opus 4.8 profile，所有模型参数沿用；
不要重新跑 29 条审核集，不追加真实 A，不把本轮数据表述为对 GA-only 的因果增益。
本轮每槽最多一次实际 Task 启动，保留原生评价结果，包括 reward=0，不因坏分数或审核不理想重跑。
真实执行和原生评价全部串行，一个槽终态、授权撤除和所属资源清理核验后才能开始下一槽。
SQLite 合成认证证明共同接线/生命周期，不证明 HTML 语义效果；真实两题各自仍需原生评价。

允许自行处理的小问题：确定性的路径分隔符、UTF-8/换行、导入隔离、明确漏传参数、纯工程接线。
修复前保存失败原件，写出根因与最小 diff，跑受影响测试和完整隔离回归；提交并推送修复，远端回读确认。
若更改被源码身份绑定的代码，必须重建匹配新源码的零模型证书，并给未启动的槽重新 prepare/授权。
不得篡改旧 frozen manifest、请求、响应、测试、奖励或证书来“继续”。

每个具体工程故障只允许一次有根因、有回归证明的修复尝试；同因仍失败就停止依赖步骤并归档，不无限试错。
Task 尚未开始且日志明确证实时，允许修复后用全新目录/run_id 再尝试该槽；旧失败和假/真授权撤除记录保留。
一旦该槽已有 Task 启动事件、真实 Task 请求或启动与否无法确认，禁止重跑该槽。
已启动后的孤立技术失败在清理明确、其它槽前提仍有效时可保留失败并继续下一未启动槽；不能补跑评价刷结果。
若后续小修导致四槽源码不一致，可以完成尚未启动的槽，但必须逐槽记录 exact SHA，明确不是严格同源码配对，不能重跑早先槽来补齐。

必须停的边界：需要改方法、提示、审核阈值、返工次数、证据规则、原题/原生测试、模型参数或已有运行预算；
需要新权限/新凭据/安装未知软件；原件或授权身份不确定；清理无法确证；秘密可能外泄。
这类不是“小工程问题”，保留已完成结果与未启动原因，撤除已生成授权，上传安全白名单诊断，不等待用户醒来前擅自扩大范围。
不得通过关闭 policy、来源绑定、证书、原断言或清理检查使运行继续。

## 四槽 prepare、逐槽一次性授权、启动和评价

先完成上文离线回归、Docker 只读预检、A/两种 B 的新源码零模型认证、证据本地提交及两种证书复核。
下面沿用上文所有环境变量；真实 profile 必须是既有真实 Task/PMA 配置，不能误用无秘密 fake profile。
不复制其内容进仓库或日志，不传 --zero-model-fixture / --candidate-profile-fixture / --stateful-fake-replies。
使用同一份历史 requested policy：uncapped Agent 时间/Task 轮数，verifier 官方限制。
这仍是诊断性运行，不是原始 Agent 时限下的官方榜单分数；不新增 token、费用或耗时限额。

真实两题历史执行使用 download_retry_v1 / max_attempts=3。下面复用该既有策略：只允许评价依赖下载重试，
不增加 Task 重跑、整个评价重跑或绕过原生断言。single_run.prepare 函数原本支持此参数，CLI 未暴露它，
故使用函数入口生成同一 frozen manifest；不是修改评价器。来源为固定 72152913… 下两题 IDENTITY.json
及 SOURCE_WINDOW_TWO_REAL_TASKS_20261025.md。若原件或实现不一致，停止，不临场创造替代评价协议。

```powershell
$TaskProfile='<用户既有真实Task配置.py>'
$PmaProfile='<用户既有真实PMA配置.json>'
$RealRoot='<全新私有四槽真实运行根目录>'
$CohortCode=(git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot freeze current source' }
# 此 HEAD 可包含已审核的本地合成证据提交；方法源码仍须匹配认证。
$Slots=@(
  @{Name='01-sqlite-gate-only'; Task='sqlite-with-gcov'; Mode='gate-only'},
  @{Name='02-sqlite-gate-one-repair'; Task='sqlite-with-gcov'; Mode='gate-one-repair'},
  @{Name='03-html-gate-only'; Task='filter-js-from-html'; Mode='gate-only'},
  @{Name='04-html-gate-one-repair'; Task='filter-js-from-html'; Mode='gate-one-repair'}
)
$PrepareAndAuthorize=@'
import argparse, hashlib, json, pathlib, subprocess, sys
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run import prepare
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.six_task_plan import validate_plan
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.citation_gate_config import verify_gate_sources
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.gate_certification import require_launch_certificate
repo, out, task, mode, official, task_profile, pma_profile, cert, policy_file, code = sys.argv[1:]
repo, out = pathlib.Path(repo), pathlib.Path(out)
head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
if head != code: raise RuntimeError('Source changed since cohort freeze')
if task not in ('sqlite-with-gcov','filter-js-from-html') or mode not in ('gate-only','gate-one-repair'):
    raise RuntimeError('Outside four-slot authorization')
requested = json.loads(pathlib.Path(policy_file).read_text(encoding='utf-8'))
if requested != {'agent_timeout':'uncapped','task_turns':'uncapped','verifier_timeout':'official'}:
    raise RuntimeError('Requested policy changed')
identity = prepare(argparse.Namespace(
    output=str(out), task=task, condition='B', occurrence=1, fake_only=False,
    research_candidate='pma_gap_evidence_v1', citation_review_gate=mode,
    official_source_git=official, task_profile_file=task_profile, pma_profile_file=pma_profile,
    certification_dir=cert, runtime_policy=requested,
    native_context_policy='required', research_capture_policy='required',
    evaluation_bootstrap_protocol='download_retry_v1', evaluation_download_retry={'max_attempts':3}))
mp = out/'manifest.json'
manifest = json.loads(mp.read_text(encoding='utf-8'))
config = manifest['config']
if manifest.get('zero_model_fixture_only') or config.get('citation_review_gate') != mode:
    raise RuntimeError('Wrong real/gate identity')
if config['runtime_policy']['requested'] != requested:
    raise RuntimeError('Frozen policy differs')
if config.get('evaluation_bootstrap_protocol') != 'download_retry_v1' or config.get('evaluation_download_retry') != {'max_attempts':3}:
    raise RuntimeError('Native evaluation download policy differs')
verify_gate_sources(config)
require_launch_certificate(manifest, fixture=False)
manifest_hash = hashlib.sha256(mp.read_bytes()).hexdigest()
if manifest_hash != identity['manifest_sha256']: raise RuntimeError('Manifest byte identity differs')
if pathlib.Path(identity['run_root']).exists(): raise RuntimeError('Run root already exists')
binding = dict(manifest['planned_order'][0], run_id=identity['run_id'],
               run_root=identity['run_root'], batch_id=identity['run_id'], config_sha256=manifest['config_sha256'])
grant = {'execution_authorized':True, 'zero_model_fixture_only':False,
         'candidate_profile_fixture_only':False, 'manifest_sha256':manifest_hash,
         'audited_code_commit':head, 'approved_arms':manifest['planned_order'],
         'run_bindings':[binding], 'run_id':identity['run_id'], 'batch_id':identity['run_id'],
         'config_sha256':manifest['config_sha256'], 'output_root':identity['output_root']}
validate_plan(manifest, grant)
with (out/'authorization.json').open('x', encoding='utf-8', newline='\n') as f:
    json.dump(grant, f, ensure_ascii=False, indent=2); f.write('\n')
# 不打印 profile 内容、凭据或授权正文，只记录可公开运行身份。
print(json.dumps({'task':task,'mode':mode,'code_commit':head,**identity},ensure_ascii=False))
'@
foreach ($Slot in $Slots) {
  $Out=Join-Path $RealRoot $Slot.Name
  $Cert=Join-Path $CertRoot $Slot.Mode
  & $Python -X utf8 -B -m "$Prefix.gate_certification" --evidence $Cert --mode $Slot.Mode
  if ($LASTEXITCODE -ne 0) { throw 'Certificate failed before real preparation' }
  $Authorization=Join-Path $Out 'authorization.json'
  # 真实子进程不得继承假传输开关；记录原值并在 finally 恢复宿主状态。
  $FixtureKeys=@('PMA_SERVICE_FIXTURE','PMA_MULTITURN_FIXTURE','POS_SYNTHETIC_FIXTURE','POS_CANDIDATE_PROFILE_FIXTURE')
  $Saved=@{}
  foreach ($Key in $FixtureKeys) { $Saved[$Key]=[Environment]::GetEnvironmentVariable($Key,'Process'); [Environment]::SetEnvironmentVariable($Key,$null,'Process') }
  try {
    $PrepareAndAuthorize | & $Python -X utf8 -B - $Repo $Out $Slot.Task $Slot.Mode $Official $TaskProfile $PmaProfile $Cert $RuntimePolicy $CohortCode
    if ($LASTEXITCODE -ne 0) { throw 'Prepare/grant failed; diagnose under bounded recovery rules' }
    & $Python -X utf8 -B -m "$Prefix.single_run" run --output $Out --authorization $Authorization --ga-source (Join-Path $Repo 'GenericAgent-main') --runtime-root $Runtime --task-profile-file $TaskProfile --pma-profile-file $PmaProfile --worker-python $WorkerPython --harbor-python $HarborPython --bench-root $Bench --official-source-git $Official --harbor-source-root $HarborSource --python-home 'cpython-3.12.12-linux-x86_64-gnu' 1> (Join-Path $Out 'controller.stdout.txt') 2> (Join-Path $Out 'controller.stderr.txt')
    $RunExit=$LASTEXITCODE
  } finally {
    if (Test-Path -LiteralPath $Authorization) { Remove-Item -LiteralPath $Authorization }
    foreach ($Key in $FixtureKeys) { [Environment]::SetEnvironmentVariable($Key,$Saved[$Key],'Process') }
  }
  if (Test-Path -LiteralPath $Authorization) { throw 'One-use authorization was not removed' }
  # 不把命令退出码或 reward 当作清理证明；逐槽读取 batch_result/live_result 原件。
  # 仅 completed 且 cleanup_confirmed=true、无所属容器/卷残留并有原生评价终态才直接继续。
  # 非零退出按上文有界规则先诊断；不得直接重复本循环/槽位。
  if ($RunExit -ne 0) { throw 'Real slot not cleanly completed; preserve and follow bounded recovery rules' }
  @'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
load = lambda p: json.loads(p.read_text(encoding='utf-8'))
identity, batch = load(root/'run_identity.json'), load(root/'batch_result.json')
if (root/'authorization.json').exists(): raise RuntimeError('Live authorization remains')
if batch.get('stop_reason') is not None or len(batch.get('arms', [])) != 1:
    raise RuntimeError('Batch did not reach one isolated terminal slot')
arm = batch['arms'][0]
run_root = pathlib.Path(identity['run_root'])
status = load(run_root/'archive/live_result.json')
if arm.get('run_id') != identity['run_id'] or arm.get('disposition') != 'completed' or arm.get('status') != status:
    raise RuntimeError('Run identity, disposition or persisted status mismatch')
if status.get('run_id') != identity['run_id'] or status.get('zero_model_fixture_only') is not False:
    raise RuntimeError('Not the authorized real run')
if status.get('cleanup_confirmed') is not True or status.get('remaining_containers') != [] or status.get('cleanup_errors') != []:
    raise RuntimeError('Cleanup is not confirmed')
volume, sidecar = status.get('owned_volume_clearance') or {}, status.get('sidecar_clearance') or {}
if volume.get('status') != 'clean' or volume.get('remaining') != [] or sidecar.get('clean') is not True:
    raise RuntimeError('Owned volume or worker clearance is not clean')
native = status.get('native_result') or {}
if native.get('status') != 'native_recorded' or status.get('native_script_observed') is not True or status.get('native_reports_checked') is not True:
    raise RuntimeError('Native evaluation was not recorded/checked')
print(json.dumps({'run_id':identity['run_id'],'disposition':arm['disposition'],'native_rewards':native.get('rewards'),'cleanup_confirmed':True}))
'@ | & $Python -X utf8 -B - $Out
  if ($LASTEXITCODE -ne 0) { throw 'Post-run identity/evaluation/cleanup check failed; no next slot' }
}
```

上面循环是正常路径，故障后不得从头重新执行它。维护单独 SLOT_STATUS.json，记四槽 not_started /
pre_task_technical_failure / task_started / completed / failed_isolated / blocked_unknown 等真实状态、所有 run_id 和 code SHA。
允许的小修后只处理符合条件的未启动槽。每次成功启动前复核冻结输入、一次性授权与实际命令，
每次结束保留原生 reward、测试通过/失败、事件/记忆/审核/返工/回执链与最终 bank；不因低分删改结果。


## Windows 字节保护补丁

collector 在每个输出认证根（例如 gate-only/、gate-one-repair/）生成 `.gitattributes`，
内容为 `* -text`；只作用于该目录及后代，并把属性文件纳入 FILE_HASHES.json。
上面的 `git add -f -- <两个证据目录>` 必须包含此隐藏文件；不要只挑JSON提交。
不得通过换行归一化重算原件哈希；不改变全局 core.autocrlf。
回归使用真实临时Git仓库，core.autocrlf=true下add/commit再新clone检出，
验证CRLF原日志、UTF-8证书、索引及属性文件字节与Git blob完全一致，目录外属性不变。
793a及其原日志保留；接收方须从最终含字节保护补丁的SHA重新生成认证材料。


## 完整诊断包一次性交付

每个运行命令执行后核对退出码；失败先停止依赖步骤，再按本文件“小问题自主修复”边界处理。不得改响应或无根因重跑。
保存原输出及未执行清单。旧 df7550644bba1598ff424c8c52b0dcf63737214a 包及旧 unknown 清理记录保持不变。
有小修时同时纳入源码 diff、根因、回归原件、修复 exact SHA 与新证书身份。成功或提前停止，都按本轮实际发生材料制作一个新 ZIP 与外部索引，建议新名称
`PMA_CITATION_GATE_FOUR_REAL_TASKS_20261028.zip`（实际日期变动时同步改名，不覆盖旧包）。

白名单包括：固定源码/环境/来源身份；两个隔离子进程原始输出、测试清单和 summary；
固定历史 policy 导出及来源哈希；Docker 只读结果；实际 A/B 夹具命令、原始日志、计划和 manifest、
execution_identity、runtime_policy_effective、worker 捕获、memory/gap/receipt 与最终 bank、
native 合成生命周期和证书核验材料；授权撤除与限定 run_id 的容器/卷清理报告；
四槽真实运行的完整请求/响应、审核/修订/回执、原生评价和可公开计划/身份或未产生说明；诊断说明及逐文件哈希索引。
原始 fixture 本机目录应保留，不能用 collector 的脱敏副本代替原始请求/回执而声称原件完整。
仅将白名单真实产生的文件纳入；逐项区分“未产生”“已产生但未收录”“已收录”，不要把缺件统称未执行。

禁止上传 profile、private_client、凭据、授权原件、秘密端点或无关个人材料。
如必需原件含秘密或白名单无法安全完整发布，停止公开上传并说明缺项，不静默改写/脱敏后宣称原始完整。
按已授权目的只提交该 ZIP 及外部索引到
`HYC-hsy/longcontext-monitor-research/pma_evidence_review/diagnostic_packages/`；
使用新归档提交、非强制推送，不上传整个工作区。
推送后重新 fetch，读取远端 exact commit 的 ZIP 字节，核对大小、SHA-256、CRC、逐文件哈希及外部索引。
返回代码 SHA、实际证据提交 HEAD、归档 SHA、下载链接、各阶段真实执行/停止状态和剩余限制。
工程回归、零模型生命周期与模型/Task 效果分别报告；本轮不运行 29 条审核集；真实模型、Task 和原生评价仅限已授权四槽，逐项报告实际发生数量及未启动项。
