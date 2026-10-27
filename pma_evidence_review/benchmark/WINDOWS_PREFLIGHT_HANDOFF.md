# Windows benchmark 离线预检修复与接收指令

## 本轮结论与边界

- 修复父版本：`c7f45915fcecfbb2f90bdaf30fe00f3bdc2769e2`。
- 上次 Windows 首轮尝试停止于预检：99 项测试执行通过，benchmark 类初始化失败，另 12 项未运行。
  独立 dataset validate 同时拒绝变动后的 MANIFEST。29 条真实审核全部未启动，不存在模型结论或评分。
- 本轮只修复平台相关的 Git 对象路径、持久化来源路径、JSON 输出换行和冻结数据检出属性。
  没有更改 SYSTEM、prompt、模型接口、解析器、标签、29 条样本或生产审核策略。
- 仍使用原始逐字节校验，绝不把 CRLF 替换为 LF 后再验 hash，不计算待验文件自己的摘要作为可信 pin。
  没有修改全局 Git 配置、读取真实 profile/凭据、调用真实模型、运行 Task/正式评价或维护记忆。
- 新增 4 项回归后，115 项完整离线测试通过。云端 Linux Python 3.12.14；**未执行 Windows 实机复验**。
  本文的 Windows 步骤正是待接收方执行的离线复验，不是已经完成的结果。

## 修复内容

1. `benchmark/core.py::checked_file` 用 `relative.as_posix()` 构造 `git show <commit>:<path>`
   和 inventory 来源路径；`build_case` 的 `origin.slot_path` 也固定 POSIX 分隔符。
   本地文件读取仍用原生 `Path`，Git 对象内容与工作树内容仍严格逐字节比较。
2. `core.write` 显式 `encoding='utf-8', newline='\n'`，保留独占创建、拒绝覆盖。
   这是写入格式固定，不是读取后规范化，也不改变 JSON 中引文的内容。
3. `benchmark/.gitattributes` 仅对下列五个冻结 JSON 设置 `-text`，阻止 Git 自动换行转换：
   `candidate_data/MANIFEST.json`、`cases.json`、`evaluation-only.json`、`inventory.json`、`requests.json`。
   没有全仓库 renormalize，也没有修改这些数据文件。
4. 11 个公开源文件继续由已有的上级 `.gitattributes` 中
   `source_window_two_real_20261025/** -text` 保护，包括根 INDEX 和两个 slot INDEX。
   新测试核对这些已有规则确实生效，而不是只保护最终 MANIFEST。

可信 MANIFEST SHA-256（保持不变）：

```text
dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928
```

冻结数据仍为 historical_original 9 + trace_derived_control 20；参考标签仍为 supported 9 /
insufficient 13 / contradicted 7。标签是开发 reference judgment，不是外部 gold。

## 回归的实际覆盖范围

`tests/test_benchmark_portability.py` 是独立测试类，不依赖旧 benchmark 类的 setUpClass：

- 使用 `PureWindowsPath` 实际调用 Git，验证对象路径与持久化路径均为 POSIX。
- 模拟 Windows 文本默认换行，验证写入 UTF-8/LF 原字节，且已有文件仍不可覆盖。
- MANIFEST、case 文件、公开源 INDEX 的换行被篡改时，原严格校验仍各自拒绝。
- 新建临时本地 Git 仓库和全新 clone，clone 的局部 `core.autocrlf=true`；未保护的控制文件实际变为
  CRLF，证明转换确实开启。五个冻结数据文件及全部 11 个来源文件仍逐字节相同。
  然后用 Windows 路径类型重建完整 29 条数据集，五个输出文件逐字节匹配冻结数据及原 MANIFEST pin。
  临时仓库只借用本地 Git 对象库，不联网、不取模型配置，不更改原仓库或用户配置。

完整输出另存 `WINDOWS_PREFLIGHT_TESTS.txt`；摘要与冻结文件比较见 `WINDOWS_PREFLIGHT_VERIFICATION.json`。
首次云端直接运行缺少现有依赖 `regex`，导致旧测试 12 failures / 8 errors；使用已有离线依赖
`/tmp/auditor-offline-deps` 后重跑完整套件通过，没有为通过而修改任何既有测试或安装新依赖。
旧 `OFFLINE_TESTS.txt` 及上次 Windows 失败诊断均保留，不被覆盖。

## Windows 接收方完整离线步骤

修复发布后，交接消息必须提供**修复的完整 commit SHA 和远端 ref**。下方两个尖括号变量是占位符，
必须替换为已核实的发布值；不得继续使用父版本 `c7f45915...` 或未核实的分支最新值。
只在已有完整仓库中 fetch 公布的修复 ref；不读取或导出任何 profile/密钥。

### 1. 保留旧失败现场，新建独立工作树

PowerShell，路径按实际存在的仓库与 Python 调整；新工作树和输出目录必须从未存在：

```powershell
$repo = 'E:\LongContext'
$py = 'E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe'
$repairRef = '<交接消息中的已发布修复ref>'
$repairCommit = '<交接消息中的40位修复commit SHA>'
$worktree = 'E:\pcitationbench_windows_fix_20261027'
$records = 'E:\pcitationbench_windows_fix_records_20261027'
if ($repairRef.Contains('<') -or $repairCommit -notmatch '^[0-9a-f]{40}$') { throw '先填写已核实的修复ref和SHA' }
if ((Test-Path $worktree) -or (Test-Path $records)) { throw '不得覆盖已有目录，请改用全新路径' }
git -C $repo fetch origin $repairRef
if ($LASTEXITCODE -ne 0) { throw 'fetch失败，停止' }
git -C $repo cat-file -e "$repairCommit^{commit}"
if ($LASTEXITCODE -ne 0) { throw '修复commit不可读取，停止' }
git -C $repo worktree add --detach $worktree $repairCommit
if ($LASTEXITCODE -ne 0) { throw '新工作树创建失败，停止' }
New-Item -ItemType Directory -Path $records | Out-Null
Set-Location $worktree
git rev-parse HEAD
git status --porcelain
git config --show-origin --get core.autocrlf
& $py -X utf8 -B -c "import sys,regex; print(sys.version); print(regex.__version__)"
if ($LASTEXITCODE -ne 0) { throw 'Python或既有依赖不可用，停止' }
```

确认 HEAD 等于公布的完整修复 SHA，工作树干净。`core.autocrlf=true` 可保留，不要求关闭。
不要在旧失败工作树中执行 reset/restore，不删除旧诊断，不用 `git add --renormalize`，不改全局配置。
旧工作树已有 CRLF 文件不会仅因新增属性自动恢复；本步骤因此要求全新工作树。

### 2. 属性、源对象和固定数据独立预检

```powershell
$pin = 'dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928'
$dataset = 'pma_evidence_review/benchmark/candidate_data'
git cat-file -e '72152913f545ca36a75b68e8796e24a6e24f9f81^{commit}'
if ($LASTEXITCODE -ne 0) { throw '缺少固定公开源commit，停止；不可自动改用新源' }
git check-attr text -- "$dataset/MANIFEST.json" "$dataset/cases.json" "$dataset/evaluation-only.json" "$dataset/inventory.json" "$dataset/requests.json"
$observed = (Get-FileHash "$dataset/MANIFEST.json" -Algorithm SHA256).Hash.ToLowerInvariant()
if ($observed -ne $pin) { throw '冻结MANIFEST字节不符，停止' }
& $py -X utf8 -B -m pma_evidence_review.benchmark validate --dataset $dataset --manifest-sha256 $pin *> "$records/dataset-validate.txt"
if ($LASTEXITCODE -ne 0) { throw '冻结数据校验失败，停止' }
```

五个 `text` 属性均应为 `unset`。若 `.git/info/attributes` 等更高优先级本机配置覆盖了仓库属性，
或任何字节检查失败，保留状态并报告；不得通过改 pin、放宽校验、自动规范化或修改用户配置绕过。

### 3. 完整离线测试与从固定来源重建

```powershell
& $py -X utf8 -B -m unittest discover -s pma_evidence_review/tests -v *> "$records/offline-tests.txt"
if ($LASTEXITCODE -ne 0) { throw '完整离线测试失败，停止' }
$rebuilt = "$records/rebuilt-dataset"
& $py -X utf8 -B -m pma_evidence_review.benchmark build --repo . --out $rebuilt *> "$records/build.txt"
if ($LASTEXITCODE -ne 0) { throw '固定来源重建失败，停止' }
& $py -X utf8 -B -m pma_evidence_review.benchmark validate --dataset $rebuilt --manifest-sha256 $pin *> "$records/rebuilt-validate.txt"
if ($LASTEXITCODE -ne 0) { throw '重建后的冻结pin校验失败，停止' }
foreach ($name in @('MANIFEST.json','cases.json','evaluation-only.json','inventory.json','requests.json')) {
  $frozenHash = (Get-FileHash "$dataset/$name" -Algorithm SHA256).Hash
  $rebuiltHash = (Get-FileHash "$rebuilt/$name" -Algorithm SHA256).Hash
  if ($frozenHash -ne $rebuiltHash) { throw "重建文件不一致：$name；停止" }
}
git status --porcelain
```

应为 115 项全部通过、两次 validate 均 `29 / valid`、五文件摘要一致、原工作树干净。
若失败，保存命令、退出码、原始日志、HEAD、Python/regex 版本、Git 属性来源和原字节摘要；
明确区分通过、失败、未运行，不把 setUpClass 错误后的 99 项当成完整通过。

### 4. 停止并回报，不自动恢复真实调用

只报告 Windows 离线工程验收结果。此次修复和离线复验不等于重新授权 29 条模型审核。
未获新的明确真实调用确认前，不执行 `run-profile`，不读取模型配置，不启动 Task/正式评价。
真实运行仍遵守 `REVIEW_HANDOFF.md` 的独立启动门禁、每项一次、不重试、工程错误立即停止及原始记录保留规则；
模型效果、标签争议和工程验收必须分开报告。
