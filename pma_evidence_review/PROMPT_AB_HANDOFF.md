# 单因素提示候选：接收、离线验收与未来真实 A/B

当前是待验证候选，不是已经证明改进的版本。生产基线 A 固定为
`77f0f91dc4f508c9ef8e39c9f01e1d50c59eebd7`；候选从归档
`f657bb866d3bbf715b37a30ca289dfb6dbea40f1` 建分支，包含原 v4 诊断包但不修改旧结果。
B 使用本次交付的完整 SHA；先核对最终回复里的 SHA，再以 detached checkout 接收。
不要把浮动分支名当实验身份，也不要把过去 7 次真实输出当本轮同条件 A/B 的 A。

## 唯一实验因素

仅 `operation_review.py` 的比较段与 STRATEGY 改变。比较要求从相关证据转为：引用实际
建立的最窄范围和条件，是否足以推出原操作已有的实质判断及强化限定；explanation 点明
必要但未证实的前提。缺少支持为 insufficient；contradicted 必须是同条件下实际不相容
证据。可由可见源码推出的窄行为仍可静态支持，不额外要求测试，不凭空构造失败或要求。

策略名 `direct-operation-v4.2-entailment-candidate`，schema 仍
`pma-operation-review-report-v2`，来源协议仍 source-use-v3。
未改输入、来源顺序、预算、操作目标、删除问题、输出示例/字段、解析/绑定、传输或模型参数。
STRATEGY 不进入 payload 哈希；真正请求变化来自比较段，测试独立重算二者 SHA256。

新增内容只有差异隔离测试和文档/原始测试日志，没有新合成语义数据集、标签、few-shot、
拆分器、用途分类或额外模型。已有测试夹具只用于流程验收。事后诊断不进入模型输入。

## 接收与离线验收（现在可以执行，不调用真实模型）

在已有仓库检出最终回复的候选完整 SHA；保留自己的未提交工作，必要时另建 worktree。
使用现有 Python 3.10+ 和现有依赖 regex==2024.11.6；不为匹配本机而重装 Python。
从候选仓库根执行：

```bash
python -m unittest discover -s pma_evidence_review/tests -v
python -m pma_evidence_review --help
```

本次实际环境 macOS / Python 3.11.15，使用现有 ../offline-deps：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../offline-deps /opt/homebrew/bin/python3.11 -m unittest discover -s pma_evidence_review/tests -v
```

75 项通过：原 73 项 + 2 项单因素隔离测试。`test_prompt_candidate.py` 从 git 读取固定 A
源码，不执行轨迹代码；逐项规范化比较完整导出计划，并验证 A/B 各自 fake 接收的 payload。
已有 CLI export/fake 一致性测试继续运行。Windows UTF8/socketpair 逻辑未改，本次非 Windows
实机验收。原始日志在 `test-records-entailment/`。浅克隆必须先取得固定 A git 对象，否则
隔离测试应报缺对象，不跳过断言。

只生成公开开发输入和请求（以下路径必须不存在）：

```bash
python -m pma_evidence_review build --repo . --sample sqlite --out sqlite-candidate-input.json
python -m pma_evidence_review build --repo . --sample html --out html-candidate-input.json
python -m pma_evidence_review export --input sqlite-candidate-input.json --out sqlite-candidate-requests.json
python -m pma_evidence_review export --input html-candidate-input.json --out html-candidate-requests.json
```

仍是 3/4 个直接操作请求，无 extract，无 --mode。完整 fake 演练见 DIRECT_HANDOFF.md；
策略字段以上述候选为准，接口不变。冻结输入摘要：

- SQLite `0aa854b8a7c7eb98ae5e412cdf78180597ca3400e0884046db397e9e4c2cdb90`
- HTML `4760d69e0e47f1e0ede15e9fd800270b89768a6307c45b4c8d4223803cc1494b`

## 未来真实 A/B（本轮未执行，必须另获授权）

先确认输入、现有模型配置和执行范围。两边使用同一现有 profile 路径/key；不显示文件内容，
不调参、不读旧诊断或对方结果作为输入、不自动修响应或重跑。不增设调用/token/费用统计
或人为上限；底层现有客户端重试行为保持。工程失败指调用/协议/解析/绑定非 ok，而不是
模型给出 insufficient/contradicted。所有日志只存新的本机私有目录，不上传公共仓库。

以下脚本可保存为仓库外的 `run_pma_ab.py`。只在明确授权之后设置环境变量并运行。
从已核对最终 SHA 的 B checkout 根目录运行；脚本固定 B=当前 HEAD，记录它，固定 A 如上。
两套 detached worktree、独立进程、cwd/--repo 明确，清除 PYTHONPATH/PYTHONHOME 防止串版本。
脚本不读取 profile 内容，只把用户给定路径交给已授权 run-profile。使用当前 Python 环境
应已具备两边所需依赖；先离线测试，不在脚本中安装依赖。

```python
import hashlib, json, os, subprocess, sys, tempfile, zipfile
from pathlib import Path

if os.environ.get("PMA_AB_AUTHORIZED") != "YES":
    raise SystemExit("Real A/B not authorized: no requests sent.")
repo = Path.cwd().resolve()
A = "77f0f91dc4f508c9ef8e39c9f01e1d50c59eebd7"
B = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
profile = Path(os.environ["PMA_EXISTING_PROFILE"]).expanduser().resolve()
key = os.environ["PMA_PROFILE_KEY"]
if not profile.is_file():
    raise SystemExit("Existing profile path missing; no requests sent.")
env = dict(os.environ)
env.pop("PYTHONPATH", None)
env.pop("PYTHONHOME", None)
env["PYTHONUTF8"] = "1"
root = Path(tempfile.mkdtemp(prefix="pma-independent-ab-"))
(root/"inputs").mkdir()
worktrees = {"A": root/"A", "B": root/"B"}
for name, sha in (("A", A), ("B", B)):
    subprocess.run(["git", "worktree", "add", "--detach", str(worktrees[name]), sha],
                   cwd=repo, check=True, env=env)
    check = ("import pathlib,pma_evidence_review.operation_review as m; "
             "assert pathlib.Path(m.__file__).resolve().is_relative_to(pathlib.Path.cwd()); "
             "print(m.STRATEGY)")
    got = subprocess.check_output([sys.executable, "-c", check], cwd=worktrees[name],
                                  env=env, text=True).strip()
    expected = "direct-operation-v4.1" if name == "A" else "direct-operation-v4.2-entailment-candidate"
    if got != expected:
        raise SystemExit("Version mismatch; no requests sent.")
archive = worktrees["B"]/"pma_evidence_review/diagnostic_packages/PMA_AUDITOR_V4_DIRECT_REAL_DIAGNOSTIC_20261026.zip"
raw = archive.read_bytes()
assert len(raw) == 270673
assert hashlib.sha256(raw).hexdigest() == "adc43e5719cbdc7a0aa1ac3766d07f79722fb1256c59c704fb611f03a6836f28"
identities = {
    "sqlite": "0aa854b8a7c7eb98ae5e412cdf78180597ca3400e0884046db397e9e4c2cdb90",
    "html": "4760d69e0e47f1e0ede15e9fd800270b89768a6307c45b4c8d4223803cc1494b"}
with zipfile.ZipFile(archive) as z:
    for sample, identity in identities.items():
        data = z.read(sample+"-input.json")  # only the frozen input, no diagnosis or responses
        assert json.loads(data)["review_input_sha256"] == identity
        (root/"inputs"/(sample+".json")).write_bytes(data)
(root/"versions.json").write_text(json.dumps({"A":A,"B":B,"input_ids":identities},indent=2),encoding="utf-8")
base = [sys.executable, "-m", "pma_evidence_review"]
# Validate and export everything before the first real request.
for sample in ("sqlite", "html"):
    for name in ("A", "B"):
        cwd = worktrees[name]
        inp = root/"inputs"/(sample+".json")
        subprocess.run(base+["validate","--input",str(inp)],cwd=cwd,env=env,check=True)
        subprocess.run(base+["export","--input",str(inp),"--out",str(root/(sample+"-"+name+"-plan.json"))],
                       cwd=cwd,env=env,check=True)
print("Fixed versions:", A, B, "Private output:", root, flush=True)
# Required serial order: SQLite A, SQLite B, HTML A, HTML B.
for sample in ("sqlite", "html"):
    for name in ("A", "B"):
        cwd = worktrees[name]
        out = root/(sample+"-"+name+"-real")
        subprocess.run(base+["run-profile","--repo",str(cwd),"--input",str(root/"inputs"/(sample+".json")),
            "--out",str(out),"--profile",str(profile),"--profile-key",key,
            "--execute-authorized-real-model"],cwd=cwd,env=env,check=True)
        report = json.loads((out/"report.json").read_text(encoding="utf-8"))
        if report["schema"] != "pma-operation-review-report-v2" or len(report["results"]) != (3 if sample == "sqlite" else 4):
            raise SystemExit("Unexpected report shape; stop, preserve output, do not rerun.")
        if any(r["engineering_status"] != "ok" for r in report["results"]):
            raise SystemExit("Engineering failure; stop, preserve output, report before any retry.")
print("Completed once. Keep private outputs for operation-by-operation diagnosis:", root)
```

授权后示例（替换既有 profile 路径和 key；本轮不要执行）：

```powershell
$env:PMA_AB_AUTHORIZED="YES"
$env:PMA_EXISTING_PROFILE="C:\private\existing-profile.json"
$env:PMA_PROFILE_KEY="your_existing_profile_key"
python C:\private\run_pma_ab.py
```

```bash
PMA_AB_AUTHORIZED=YES PMA_EXISTING_PROFILE=/private/existing-profile.json PMA_PROFILE_KEY=your_existing_profile_key python /private/run_pma_ab.py
```

上述脚本只检查每次完整 CLI run 返回后的工程状态；当前审核器会在单个 run 内继续报告其余
操作错误，这是 A/B 两边既有行为，不在本轮修改。发现失败后停止后续 run，不自动重试。

## 如何比较，不把支持率冒充准确率

以 sample/cycle/op_index/action/memory_id/revision/content hash 对齐，比较完整操作的
verdict、理由、引用真实建立的范围与缺失前提。记录误放是否下降、原本可支持的窄行为是否
保留、是否把未知误判反驳；每个判断需回到当时可见材料，保留争议，不称盲评 gold。
两份样本是开发样本，不报告泛化或效果增益。补证敏感性不能从本轮固定输入 A/B 推断：
之后可单独设计正反成对补证及留出样本，独立冻结/授权，不能夹带进当前单因素实验。
