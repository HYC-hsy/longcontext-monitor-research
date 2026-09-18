# 长程 Agent 的任务状态失真与持续监察

最新审阅入口：[独立核验能力原型与专家问题（2026-09-18）](docs/INDEPENDENT_VERIFICATION_EXPERT_REVIEW_20260918.md)，随后看[测量修复与标签复核](docs/INDEPENDENT_VERIFICATION_MEASUREMENT_REPAIR_20260918.md)及[2026-09-19 传输诊断](docs/INDEPENDENT_VERIFICATION_R4_TRANSPORT_DIAGNOSTIC_20260919.md)。这是离线局部试验；尚无完整面板结果，也未改在线监察流程。

这是供受邀研究者讨论的**研究中快照**，不是论文最终实现或已验证的方法发布。希望大家帮助我们质疑设计、解释失败和选择下一步，而不是只评价成果展示。

## 阅读顺序

### 最新代码更新：续接诊断与有限恢复（尚未真实验证）

当前源码为本地 `ff86393`，包含续接用途边界修复和诊断阶段 `db6f066`。
请先读 [诊断A](docs/archive/CONTINUATION_DIAGNOSTICS_A_20260917.md) 和
[有限恢复B](docs/archive/CONTINUATION_BOUNDED_REPAIR_B_20260917.md)。
新增停止原因保留、校验前本地响应归档、固定失败原因码及一次格式恢复；不改
根判断/simple指导、PMA记忆与调度。137项相关离线回归通过，不等于真实恢复有效。
新测试及其续接夹具已附；依赖完整宿主目录的测试仍不能在本快照中直接全跑。
请重点审查失败响应不执行工具、重试预算/取消、历史与控制动作不重放、停止原因校验。
本包没有上传原始续接响应；没有新实验结果。以下R1轨迹仍来自修复前的 `eb6d7cd`，
不能当作新代码运行证据。旧manifest仅作历史/计划记录，重跑前需生成新hash和run-id。

### 2026-09-18 更新：根判断 decision R2 真实运行

请读 [R2审计](docs/archive/ROOT_DECISION_R2_AUDIT_20260918.md) 和
[R2过滤轨迹](evidence/root_decision_fyne_r2)。同题运行已正常结束，原生结果为 2/7。
续接路径在真实运行中完成了一次有限格式修复；根判断实际进入模型，但仍把“编译通过＋局部函数存在”
扩大为全局完成。该结果不能证明 decision 候选有效，simple 对照使用同一修复版本和新 run-id。

### 最新：根判断候选 R1（异常终止，无有效评分）

请先读 [本次审阅入口](docs/archive/ROOT_DECISION_R1_EXPERT_REVIEW_20260917.md)，
再看 [轨迹与失败回执](evidence/root_decision_fyne_r1)。执行版本为 eb6d7cd。
根判断合同尚未触发，监察者在普通 review 的续接阶段失败；不能据此评价候选效果。
同题简单公共检查对照已准备但未启动，计划排查共享工程故障后继续比较。
下方 R9 内容是前一轮历史，不是本次结果。

### 2026-09-17 更新：R9

优先阅读 [R9审计](docs/archive/PMA_PHASE_HANDOFF_R9_AUDIT_20260917.md) 和 [交接修复](docs/archive/PMA_PHASE_HANDOFF_REPAIR_20260917.md)。源码更新到本地46ba27f；R8保留作对照。
R9阶段拒绝降为0，三次纠偏后都有局部修复，但最终仅1/7通过，仍从局部成功跳到全局完成；不能称效果提升。任务方的验证主要为格式化/列文件/echo，监察者未执行编译或测试。请重点审计决定范围与证据范围之间的缺口。
新轨迹位于 [automatic_fyne_r9](evidence/automatic_fyne_r9)，其中decisions保留原始行号、task_commands展示任务方实际执行的检查命令。当前只是协议修复，尚未加入Judgment Record候选。

1. [研究问题与当前方法](docs/RESEARCH_AND_METHOD.md)
2. [困难、失败与希望得到的建议](docs/OPEN_PROBLEMS.md)
3. [证据说明](evidence/README.md)，再查看 R8 决策和人工干预原件
4. [代码与复用边界](docs/CODE_AND_REUSE.md)

历史R8在Fyne 2.2中两次有效纠偏，最终2/7；最新R9三次局部纠偏，最终1/7。两轮都存在不充分依据的根完成。我们不将“动态记忆＋主动提醒”本身作为尚无人研究的新贡献。

本仓库最初为私有研究审阅包，2026-09-17核对时已为公开仓库；此更新不改变可见性。材料用于研究审计，不应用于benchmark训练/调优。没有附密钥、原开发仓库Git历史、隐藏测试或完整历史对话。源码快照保留历史可选模块以避免破坏依赖，不表示所有模块都在当前候选中启用。

## 能运行到什么程度

核心源码位于 `src/monitor_agent_core`，用于审阅和离线工程测试。配置 Python 环境并安装 requests、shortuuid、pytest 后，可在仓库根目录用 PowerShell：

```powershell
$env:PYTHONPATH = (Resolve-Path ./src).Path
python -m pytest tests/test_monitor_pma_fused.py -q
```

本包不包含完整 GA/Harbor/Docker 任务运行基础设施，不能据此一键复现论文成绩。适配层依赖 GA 的 research_runtime，作为接口审阅材料而非独立可运行脚本。不要在真实主机上随意运行监察者生成的 code_run；其本身不是安全沙箱。
