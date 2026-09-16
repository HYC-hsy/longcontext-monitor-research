# 长程 Agent 的任务状态失真与持续监察

这是供受邀研究者讨论的**研究中快照**，不是论文最终实现或已验证的方法发布。希望大家帮助我们质疑设计、解释失败和选择下一步，而不是只评价成果展示。

## 阅读顺序

1. [研究问题与当前方法](docs/RESEARCH_AND_METHOD.md)
2. [困难、失败与希望得到的建议](docs/OPEN_PROBLEMS.md)
3. [证据说明](evidence/README.md)，再查看 R8 决策和人工干预原件
4. [代码与复用边界](docs/CODE_AND_REUSE.md)

当前自动候选在 Fyne 2.2 一次运行中有两次有效纠偏，但最终只通过 2/7 个评价阶段；仍误把局部问题修复当作整题完成。我们不将“动态记忆＋主动提醒”本身作为尚无人研究的新贡献。

本包仅供私有 GitHub 仓库内的受邀研究讨论。不要转发日志或用于 benchmark 训练/调优。没有附密钥、原开发仓库 Git 历史、隐藏测试或完整历史对话。源码快照保留历史可选模块以避免破坏依赖，不表示所有模块都在当前候选中启用。

## 能运行到什么程度

核心源码位于 `src/monitor_agent_core`，用于审阅和离线工程测试。配置 Python 环境并安装 requests、shortuuid、pytest 后，可在仓库根目录用 PowerShell：

```powershell
$env:PYTHONPATH = (Resolve-Path ./src).Path
python -m pytest tests/test_monitor_pma_fused.py -q
```

本包不包含完整 GA/Harbor/Docker 任务运行基础设施，不能据此一键复现论文成绩。适配层依赖 GA 的 research_runtime，作为接口审阅材料而非独立可运行脚本。不要在真实主机上随意运行监察者生成的 code_run；其本身不是安全沙箱。
