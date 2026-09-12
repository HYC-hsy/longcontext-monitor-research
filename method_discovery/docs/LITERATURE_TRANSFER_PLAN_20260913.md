# 文献机制适配与选择性并发

本轮经用户要求补齐上一轮未完成的机制迁移。回退点 tag `pre-literature-mechanism-transfer-20260913` 指向771bc85。继续做到真实实验启动前，不自动执行；单步代码新增删除不超过600行，逐阶段Git。已有时效提示不是本轮主体。

## 顺序与验收

1. 深入审计异步/混合控制及输入维护的论文和作者代码，记录身份、许可与具体可复用对象。研究问题仍为表示遗漏和错误闭合。
2. 复用PMA的BM25代码与LivePlan的轨迹类型/格式化代码，在独立监察者中适配按需决策视图：原任务、自然working state、查询相关私有笔记、最新或纠偏以来的原始公开行为。保留通用文件和执行工具，不要求固定状态ID。原始材料仍可直接回查，无新增持久语义事件层。与旧focus/inquiry的区别是统一任务与记忆检索、按公开原始内容呈现，而非另一个待填表单。
3. 可关闭的混合控制：普通执行并发；同一监察者可显式短暂停、调查、纠偏恢复；不设置逐轮模型批准、不自动停止所有UNKNOWN。GA取消/输入通道复用；接口桥接属于本地适配，不冒称复用LivePlan整个阻断算法。失效租约、关闭/故障释放、暂停期间不能等任务新行为等由工程保证。
4. 单独回归、组合假模型集成、关闭开关回归、源码和许可核验、隔离入口透传和无API预检；准备共同Fyne题的单次候选，真实启动前停止。真实效果、成本、时效改善未测，不冻结方法。

## 控制约束的本次例外

2026-09-13用户明确允许部分停止、部分并行。因此混合候选允许监察者自主请求有限暂停以防已识别问题扩散；默认关闭，纯并发对照保留。这不授权恢复每轮同步审批、不授权第二个监察者或在线checker，也不授权不可逆回滚任务文件。暂停不是事务回滚或瞬时终止所有工具的保证。

## 关键来源

- [LivePlan](https://arxiv.org/html/2608.06701v1)，§II-A–C；[作者代码](https://github.com/Intelligent-CAT-Lab/Agent-Planner)，c16797a09b964f901b34fe3da430ee011a5cc660，MIT。原始formatters/types复用；原rule monitor绑定shell阶段与图，不把规则分类器直接当我们的语义判断器。
- [Wink](https://arxiv.org/html/2602.17037v2)，§3与7。后台周期观察，结果可用才注入，报告延迟导致建议冗余和复杂多轮恢复困难。未找到可核验作者运行源码，不冒称复现。
- [COCO](https://arxiv.org/html/2508.13815v1)，CRM/BRP；保留纠偏上下文、允许执行者检验批评，而非监察结论天然正确。未确认官方仓库；其复杂度主张不作为本方法保证。
- [EmbodiedAct](https://github.com/thu-coai/EmbodiedAct)，真实stream pump、疑点steer、严重时abort、L2后台consult；domain probes和多模型不直接适配。pyproject明确License to be added，仅阅读不vendoring。
- [PMA](https://github.com/yifannnwu/proactive-memory-agent)，89e5c0d6aadfe531a1aee42fd290d48be89973dd，Apache-2.0；检索代码原样使用，不声称仅BM25就复现PMA的双phase。
- DPT、Async Control、SimpleMem、LangChain工程的详细边界沿用MEMORY_ASYNC_RESEARCH_AND_OPTIMIZATION_20260913.md。不是所有公开代码都适合移植，不以拷贝数量代表创新。

## 人工依据

重新读取人工Fyne原始011/014：先核测试oracle与原要求是否一致，再给最小控制实验；测试通过后释放局部关注而非无限加测。该行为要求同时看到任务、上次判断、后续行为及具体测试，不是仅给一个“文件变了”的提示。原路径见PHASE1_MANUAL_FYNE_REFERENCE_AND_CONTINUITY_CHANGE_20260907.md；人工结果不是自动机制效果证据。
