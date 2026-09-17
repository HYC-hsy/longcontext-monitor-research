# 长程 Agent 的任务状态失真与持续监察

这是供受邀研究者讨论的**研究中快照**，不是论文最终实现或已验证的方法发布。希望大家帮助我们质疑设计、解释失败和选择下一步，而不是只评价成果展示。

## 阅读顺序

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
