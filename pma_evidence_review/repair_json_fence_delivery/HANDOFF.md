# PMA 单次返工 JSON 围栏窄修复

基线：a250c8aedf61a85f91ec72532ab6e8c02df96617（包括当前实际方法代码及四槽脱敏归档）。
最终发布 SHA 以交付回复为准；不要从旧8c分支重写。保护用户工作树，在新worktree接收。

生产改动只有 gate_control.repair 使用现有 review.json_value 代替 citation_inputs.strict_json。
后者全局规则不改；review.json_value、所有提示/模型参数/引用策略/停止规则不改。
复用原审核器的外层包裹解析，不增加纠错、抽取器或语义宽容。

仅接受原行为范围：裸JSON，或完整且唯一的 ```json\n…\n```（外部空白允许）。
不接受散文前后缀、残缺/多个围栏、多个JSON对象、其它语言/大写语言标签、CRLF围栏。
重复键仍拒绝；后续replace/withdraw精确schema、字段类型、固定目标、引用绑定仍执行。
返工最多一次；成功解析只生成候选，二审supported才发布。准备不足或二审拒绝不发布。
未知字段/非法目标仍是工程失败并停止本批后续操作。原始响应文字保留围栏，不重写。

## 真实响应离线回放

公开ZIP位置：pma_evidence_review/diagnostic_packages/PMA_CITATION_GATE_FOUR_REAL_TASKS_COMPLETE_V2_20261028.zip
16938429 bytes，SHA256 4e14d6241dc7588ae5817fce40a23da233b75a2d41bc32039b5c84eb7b468b8e。
只在内存读取四槽中两个repair槽的gate_cycles/responses压缩成员，不执行任何轨迹代码。
按正式error_code=repair_parse_failure选择；以audit_request_sha256唯一联结responses，
要求报告raw_response与响应文字相同。SQLite12项、HTML2项均复现旧裸JSON失败，
经当前repair真实schema路径成为合格候选；无语义调用、无记忆写入。

REPLAY_INDEX.json含14项成员路径、source_line、归档保留的source_line_sha256、
实际投影响应文字SHA256及响应压缩成员SHA256。不新增原响应正文夹具、不上传整包副本。
此ZIP是脱敏投影；保留的source_line_sha256不能当作当前投影行哈希，
audit_request_sha256也不是宣称全部原始请求可由此逐字重建。
历史真实结果保持repair_parse_failure；离线schema通过不能追溯改成真实执行成功。

## Windows接收及测试（仅离线）

```powershell
$Repo='<现有仓库目录>'
$Sha='<交付回复的最终exactSHA>'
$Worktree='<不存在的新修复验收工作树目录>'
git -C $Repo fetch origin repair/pma-repair-json-fence-20261028
if ($LASTEXITCODE -ne 0) { throw 'fetch failed' }
git -C $Repo -c core.longpaths=true worktree add --detach $Worktree $Sha
if ($LASTEXITCODE -ne 0) { throw 'worktree creation failed' }
Set-Location $Worktree
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:LITELLM_LOCAL_MODEL_COST_MAP='True'
# 使用接收方已有依赖齐全的Python3.12+与固定native Harbor，不安装/更改配置。
$Python='<已有Python3.12+可执行文件>'
$NativeHarbor='<固定459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc的native Harbor源码目录>'
$Reports='<全新离线报告根目录>'
New-Item -ItemType Directory -Path $Reports -ErrorAction Stop | Out-Null
& $Python -m pma_evidence_review.tests.run_gate_regressions --native-harbor-source-root $NativeHarbor --report-dir "$Reports/isolated"
if ($LASTEXITCODE -ne 0) { throw 'Isolated regressions failed; preserve raw reports, stop' }
# 再输出历史响应的安全定位/哈希索引；文件必须不存在。
& $Python -m pma_evidence_review.tests.test_repair_json_fence --out "$Reports/REPLAY_INDEX.json"
if ($LASTEXITCODE -ne 0) { throw 'Archived schema replay failed' }
```

不要向这些命令传profile，不运行single_run/Harbor fixture/Task/官方评价/真实模型。
本目录.gitattributes仅在目录内禁用Git文本转换，保护已存日志/索引字节；不改全局Git配置。
重复执行使用新报告目录，不覆盖原件。

## 本机验证范围与限制

机器有Python3.11.15及Python3.12.13；既有项目测试依赖只在3.11目录可用。
没有安装依赖或修改runner以凑通过。
完整隔离runner原样执行：PMA verifier身份预检在3.11遇固定Harbor3.12语法错误，
退出2；native子进程1项明确skip；总体退出1。原始日志/子进程清单保留在isolated/。
这不是“完整回归通过”。接收方/父线程Python3.12+必须独立跑上述完整runner。

另用原runner的同一PMA suite_manifest做补充执行，采用既有PMA-only导入兼容、
socket禁网，不执行Verifier身份预检；这份结果只能称补充PMA回归，不替代隔离runner。
TARGETED_TESTS.txt为新增边界/14回放/fake二审闭环；PMA_SUPPLEMENTAL_PY311.txt为补充全清单。
无真实模型、Task、官方评价、正式记忆调用；没有方法效果结论。主张拆分未实现。
