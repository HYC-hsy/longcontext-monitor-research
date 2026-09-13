# LongContext 开发协作规范

## 临时研究主线硬约束（方法发现完成后经用户确认删除或替换）

本节用于防止上下文压缩或线程切换导致研究问题再次漂移。在方法发现阶段完成、最终方法冻结并经用户确认之前，本节优先约束 `E:\LongContext` 下的相关研究和实现。

### 权威文档

- 2026-09-14 用户确认 PMA 与自主监察内部融合，工程入口 `method_discovery/docs/PMA_AGENT_FUSION_IMPLEMENTATION_20260914.md`。开启 `GA_MONITOR_PMA_MEMORY` 时采用作者 process 内部的维护/判断工具循环，不再前置 PMA 后追加第三层 review。复用作者原提示构造、bank 操作与提醒解析；判断阶段可用同一操作修订 bank，提醒直接投递并续接观察。独立 task_model 候选退役并显式拒绝旧开启配置；保留原任务、连续 History、原始工具和 follow/patrol 控制。旧实现保存在 `pre-pma-agent-fusion-20260914` 标签；不恢复兼容串接。真实效果未验证，启动需独立确认。

- 2026-09-13 用户批准任务理解与局部修复分离候选，入口 `method_discovery/docs/TASK_UNDERSTANDING_SEPARATION_20260913.md`。`GA_MONITOR_TASK_MODEL=1`（默认关闭，需PMA维护）在已有首次维护调用生成自然 task_model.md，原任务保留完整权威原文并由模型文件引用；后续进度不自动覆盖任务理解，根完成/交接重新提供原文。无新调用阶段、不改控制链，121项工程检查通过，真实效果未验证，启动须另确认。

- 2026-09-13 用户批准小幅文件入口修订，见 `method_discovery/docs/MONITOR_FILE_OVERVIEW_IMPLEMENTATION_20260913.md`。已移除模型工具 review_context；原 decision-context 开关现选择自动更新的 monitor/overview.md 文件入口，模型用通用读文件/代码工具查看。working.md 仍由同一模型自然维护，不重复自动注入其正文；概览只导航，不判定完成。PMA 两阶段、持续 History 与 follow/patrol 本轮不改。尚未真实验证，不得据工程测试认定效果。

- 2026-09-13 R2后最小原要求优先候选，入口`method_discovery/docs/PMA_REQUIREMENT_FIRST_TIMED_EVIDENCE_20260913.md`。PMA适配层维护要求/声明/带时序观察，不提前裁决完成；比较先从原要求确定支持尺度再看记忆。任务公开归档新增时间元数据，监察输入展示调用/返回时间，旧/重叠观察不当作写入失败。作者process/bank不变，follow/patrol不变；仅工程验证，真实启动另确认。

- 2026-09-13 用户批准最小判断依据适配与等待修复，入口`method_discovery/docs/PMA_JUDGMENT_BASIS_AND_FOLLOW_REPAIR_20260913.md`。wait默认follow保持并发观察且不重复取消；显式patrol离开局部调查，后续醒来仍先停止。PMA保留作者两阶段执行，仅适配判断依据提示及命令—输出来源；不称原提示复现，不以工程通过证明效果，真实启动另确认。

- 2026-09-13 用户批准完整PMA记忆执行链候选，入口`method_discovery/docs/PMA_TWO_PHASE_INTEGRATION_20260913.md`。现`GA_MONITOR_PMA_MEMORY`调用作者原MemoryAgent.process两阶段并将提醒交给现有持续监察者；no_intervention不代表完成或自动静默。近期输入按真实task_turn映射作者窗口，保留原始证据边界；不是原论文完整实验复现，不改任务控制顺序。每wake两次额外同模型调用，分别归档成本。旧第一阶段版本保存在Git；真实启动另确认。

- 2026-09-13 用户批准PMA第一阶段维护机制接入独立监察者候选，入口`method_discovery/docs/PMA_MEMORY_MAINTENANCE_ADAPTATION_20260913.md`。`GA_MONITOR_PMA_MEMORY`默认关闭，复用作者记忆操作/提示/检索代码，第二阶段仍为现有持续有工具监察者，不称完整PMA复现。每wake增加一次同模型维护调用并记录成本；不改已确认控制顺序、两层观察或在线信息边界。工程验收不表示效果成立，真实启动另确认。

- 2026-09-13 独立性补齐：`method_discovery/docs/MONITOR_HOST_INDEPENDENCE_COMPLETION_20260913.md`。内核配置必须显式传入路径，不得推断GA目录或回退mykey；GA事件字段/summary解析和任务侧原要求文件由ga_monitor_adapter负责。独立包可单独安装；运行归档绑定task_id、任务摘要和工作区。当前Claude监察profile为claude_monitor_opus48，真实密钥只在忽略的monitor_config/models.local.json。框架独立不等于共享容器下的OS权限隔离，不得混称。

- 2026-09-13 用户纠正首次停止点并授权实现：停止由“静默→唤醒”触发，而非流式intervene选择。初始化与静默后的首次审议先安装宿主屏障，收到确认后调用监察模型；首条纠偏送达或wait后恢复任务，活跃局部跟进中的模型调用继续并行，不重复安装屏障。新实现见`method_discovery/docs/WAKE_OWNED_CONTROL_IMPLEMENTATION_20260913.md`，覆盖下方冲突的“发现问题后才停止”措辞。无pause工具，不改变无checker边界；异常显式释放。PMA等待位置已核对，但其完整维护逻辑不作为Clean母体。

- 2026-09-13 用户进一步确定工程调度：正常并发监察发现有公开证据的问题后，先由工程停止任务 Agent，再完成并发送首次纠偏；纠偏送达后恢复任务执行，进入并行的持续纠偏循环，主动跟踪后续理解、意图和行动，发现再次偏移即中断纠正，确认局部理解与行为恢复后才静默。不得要求模型额外调用pause/resume工具，不得把后续循环改成逐轮等监察LLM审批。本裁决覆盖下方“新调度尚待选择”及旧主动暂停条款；规定的是目标行为，不表示已经实现或保证零延迟。工程负责停止、送达、恢复与异常退出，模型负责基于公开证据判断问题和纠偏内容；识别依据如何交给工程须在接线设计中明确，不能靠文本关键词猜测。普通未发现问题的调查仍并发，不能把所有UNKNOWN作为停止信号。

### 作者运行代码优先（用户提高优先级，2026-09-13）

- 在上述研究边界与已确认控制顺序内，复用优先级为：作者原始运行代码直接接入 → 保留作者核心逻辑的必要适配 → 无可用实现时才自行实现。不得把“参考了思想”“复制了格式化工具”当作已复用控制机制，也不得因为重写更方便而跳过可用作者实现。
- 实施前必须读作者实际执行入口、调用链、状态更新、阻断/恢复及异常分支，而不只读论文描述、README或类型定义。记录仓库、commit、许可证、具体函数及本地接入位置；可独立复用的功能尽量连同原测试和许可保留，适配层与作者代码分离。
- 必要适配限于宿主接口、数据形状、路径、模型接口与已确认并发语义；不得无说明改掉作者的核心调度后仍称原样复现。需要替换核心判断/规则时，明确属于新机制，并报告差异与理由。
- 没有公开代码、许可不允许、实际代码不具备所声称能力，或原实现与本项目控制顺序不兼容时，应给出源码证据，说明能复用和不能复用的部分。不得假造作者实现、把同步non-blocking称异步并行，或为复用而引入无关框架、领域规则、额外模型和在线checker。重大冲突按决策门禁处理。
- 验收同时检查作者逻辑保持与本地闭环接线：首次停止先于纠偏送达，送达后恢复并行，后续纠偏可中断且不丢消息，普通监察阻塞不冻结正常执行；并验证异常不会留下无主暂停。工程保证的是控制顺序与生命周期，不是百分百识别所有偏移或模型零延迟。真实效果仍由完整任务验证。

- 2026-09-13 R2后用户否决模型调用task_control申请暂停，要求确定的控制行为由工程保证。已撤销该工具、提示与租约路径，旧HYBRID_CONTROL=1启动显式报错；即时纠偏和根完成控制保留。来源纠正：LivePlan的blocking/non-blocking是执行前阻断/执行后建议，已读源码为同步调用，不能称后台并行。新工程调度尚未实现，不能未经确认引入其领域规则或恢复逐轮LLM审批。当前清单见`method_discovery/docs/MONITOR_CONTROL_ROLLBACK_AND_INVENTORY_20260913.md`。此条覆盖下方旧主动暂停裁决；历史manifest不修改、不重用。

- 2026-09-13 R1真实适配诊断后，用户要求把机制使用方式也纳入优化。R2入口`method_discovery/docs/LITERATURE_TRANSFER_ADAPTATION_R2_DESIGN_20260913.md`：decision_context开启时，正常模型请求临时可见已有第一层synopsis小窗口与上次纠偏，详细原始证据仍主动查询；不增加第三层、不逐事件唤醒、不把全文packet自动注入、不强制用工具或暂停。轻量可见面与有界检索同属本候选，未证明独立效果。R1已停止，禁止复用其run-id重跑；R2真实启动仍须确认。

- 2026-09-13 用户批准补齐文献机制迁移，并允许部分暂停、部分并行；执行入口 `method_discovery/docs/LITERATURE_TRANSFER_PLAN_20260913.md`。`GA_MONITOR_HYBRID_CONTROL` 是默认关闭的选择性有限暂停候选，不是逐轮审批；正常监察仍并发、只有同一监察者自主请求才暂停，纠偏/静默/故障/租约到期恢复。`GA_MONITOR_DECISION_CONTEXT` 独立控制按需原任务、记忆与原始行为视图。不得据工程通过宣称有效或替换原研究问题；真实启动仍须确认。原live-awareness准备分支暂停，不自动启动。

- 2026-09-12 用户批准PMA保留原同步维护—提醒调度作为独立外部基线；此例外仅用于GA_PMA_ENABLED，不改变Clean主体并发硬约束。实现见`method_discovery/docs/PMA_SYNC_IMPLEMENTATION_20260912.md`；称PMA同步GA机制适配，不称原论文原样复现。两者互斥，PMA仍无在线checker且真实启动独立确认；工程通过不表示效果成立。

- 2026-09-11/12 无API静态准备子阶段：`method_discovery/docs/PAPER_P1_EXECUTABLE_RESEARCH_CONTRACT_20260911.md` 与 `PAPER_STATIC_INVENTORY_20260911.json` 给出拟议6题面板、G0/G1/G2/G3差异、指标分母和验收出口。六题是5道旧Roadmap dev_pilot加Fyne诊断题，不替代原跨来源/holdout门禁，未批准整批运行；PMA并发适配选择、原生评分映射、完整源码身份和资源门禁尚未完成。静态脚本/5项工程测试不是方法效果证据，生产监察机制未改。

- 2026-09-11 用户要求按论文最终实验倒推研究，暂停局部补丁式扩张；当前获授权的是不调用模型的调查与规划。新入口：`method_discovery/docs/PAPER_EXPERIMENT_EVIDENCE_AUDIT_20260911.md`、`PAPER_EXPERIMENT_BLUEPRINT_20260911.md`、`REPRODUCTION_READINESS_CARDS_20260911.md`。已核对文献实验设计、Final120元数据和部分复现入口；未完成原论文效果复现。后续先固定强基线、题源/预算/比较协议，再选择最小机制；不以API恢复自动重启旧候选队列。新增题源、TB版本、规模和投稿倒排均为待确认建议，不改变现有划分/真实启动门禁，不默认为批准实施全部阶段。

- 2026-09-11 用户裁决禁止目标版本官方源码/测试等参考答案泄露。后续 Clean Monitor 真实运行必须使用 `no-network-unix-inference-v1` 隔离配置：任务与监察者同处无网络容器，固定推理/遥测 Unix socket 通道、干净运行副本、无旧轨迹挂载。不得用 PUBLIC 加 allowed_hosts 冒充白名单，也不得因联网失败退回公网。实现与验收见 `method_discovery/docs/PHASE1_OFFLINE_ISOLATION_IMPLEMENTATION_20260911.md`。旧 tool-feedback R2 的7/7仅作泄露诊断，不作干净效果证明。正式启动仍需确认；隔离后的基线和候选应重新比较。

- 2026-09-08 系统性优化的设计入口：`method_discovery/docs/PHASE1_COHERENT_MONITOR_OPTIMIZATION_DESIGN_20260908.md`。
  当前完成 S0 设计，未修改执行代码或启动新实验；S1 连续认知底座与 S2 可修订判断依据须分开验收。
  保留通用工具、同会话、两层观察与并发，不通过重复提示原则或领域规则替代机制判别；不覆盖五阶段研究路线。

- 2026-09-07 人工 Fyne 复盘后，用户授权基础观察/回执修复与最小认识续接候选实现；真实启动仍需单独确认。
  复用人工经验时先读 `method_discovery/docs/PHASE1_MANUAL_FYNE_REFERENCE_AND_CONTINUITY_CHANGE_20260907.md`，
  再按其中原始轨迹与干预锚点核对；不得把人工结果视为自动候选或非线性记忆的有效性证明。

- 2026-09-06 用户确认的后续方法发现路线：`method_discovery/docs/METHOD_DISCOVERY_HYPOTHESIS_DRIVEN_PLAN_20260906.md`。以 Clean Monitor 为主体，按关键原因发现、最小机制、长程持久性、收束解释、冻结正式实验五阶段推进，覆盖旧路线冲突的后续执行顺序；聊天 N0–N9 不作为执行规格。当前仅授权阶段 1 历史调查。研究问题 A–D、无 checker、两层观察、单一持续监察者、真实启动门禁和 600 行限制保留；成本贯穿全程。阶段 1 首批证据见 `method_discovery/docs/PHASE1_CAUSAL_EXPLORATION_INITIAL_FINDINGS_20260906.md`，尚未完成因果判别。

- 论文主规格：`some_research/12_updated_paper_thesis_and_method_candidates.md`。
- 实证依据：`some_research/11_final120_empirical_pivot.md`。
- 形成脉络：`some_research/13_research_genealogy_to_evidence_carrying_state.md`。
- 无 checker 约束修订：`some_research/14_no_checker_realignment_and_method_convergence.md`。该文件只修正在线证据假设，不得替代 `12` 的研究问题和创新 A–D。
- 单一持续监察者架构裁决：`some_research/15_single_monitor_deliberative_control_realignment.md`。默认使用同一个监察者与持久双层状态；小模型维护只允许作为成本消融，不是核心方法依赖。
- 当前阶段顺序：`method_discovery/docs/METHOD_DISCOVERY_REDESIGN_PROPOSAL_20260821.md`。该文件虽保留 proposal 文件名，但已于 2026-08-21 经用户确认成为暂行权威设计；旧的 `METHOD_DISCOVERY_REVISED_STAGES_20260818.md` 仅保留为历史记录。
- 干净监察者重建：`method_discovery/docs/C1_CLEAN_MONITOR_AGENT_FOUNDATION_SPEC_20260901.md` 定义基础边界，`C2_CLEAN_MONITOR_AGENT_FOUNDATION_REPORT_20260901.md` 与 `C3_CLEAN_MONITOR_TASK_AGENT_INTEGRATION_REPORT_20260901.md` 记录基础内核和首次任务侧接线，`C4_MONITOR_SOURCE_INDEPENDENCE_REPORT_20260901.md` 是源码独立化裁决，`C5_MONITOR_INTEGRATION_HARDENING_REPORT_20260901.md` 记录完成边界、最终公开证据、宽窗口压缩、用量落盘与 GPT-5.6-sol 连通修复，`C6_MONITOR_PROTOCOL_AND_ENTRY_HARDENING_20260902.md` 记录跨唤醒工具协议、按完整 review 压缩与干净真实任务入口。当前实现位于独立 `GenericAgent-main/monitor_agent_core/` 包，核心源码不得依赖 `ga`、`agentmain`、`agent_loop`、`llmcore`、`mykey`、`research_runtime`、`experiment_conditions` 或 GUI/Web/Reflect；GA 特有的事件、强制中断和 completion 类型转换只能位于 `ga_monitor_adapter.py`。`code_run` 按 2026-09-01 用户裁决暂保留本地通用执行，不得宣称具有硬文件系统隔离。真实任务只允许使用 `GA_MONITOR_*` 和 `clean_monitor_prepare_real_task_gate.py`；`GA_M0_MONITOR_*` 已退役并 fail-fast，旧 M3 manifests 仅作历史证据。新实现使用两层任务观察、同一监察者持续会话、独立进程、可恢复强制中断和同会话纠偏。C6 仅获得确定性工程验收，未经独立启动门禁不得据此声明真实任务效果。
- 交互感知选择逻辑：`method_discovery/docs/METHOD_DISCOVERY_INTERACTION_AWARE_SELECTION_REVISION_20260822.md`。该文件修订 R1–R7 的候选筛选与淘汰方式，不改变研究问题和创新 A–D。
- Real-task-first 阶段修订：`method_discovery/docs/METHOD_DISCOVERY_REAL_TASK_FIRST_REVISION_20260822.md`。该文件是当前最高优先级的方法发现执行规划，覆盖前两份规划中冲突的 R1–R7 顺序、候选晋级门禁和离线实验权限；旧文档继续保留贡献定义、理论脉络和历史结果。
- M0 人工能力上界阶段：`method_discovery/docs/M0_HUMAN_CAPABILITY_UPPER_BOUND_STAGE_20260822.md`。该阶段已于 2026-08-22 经用户确认，当前执行优先级高于旧 R1–R7 组件顺序：先在完整真实任务中建立不限成本、可在线暂停和多轮纠偏的持续监察者能力上界，再依据其真实成功与失败形式化、消融和降本。它不改变研究问题、创新 A–D 或无 checker 边界。
- M0 递增演化路线：`method_discovery/docs/METHOD_DISCOVERY_M0_EVOLUTIONARY_ROADMAP_20260824.md`。该文件于 2026-08-24 经用户确认，是 M0-v1 冻结后的最高优先级执行规划：M0-v1 是唯一可运行母体和回退点；后续版本只在上一接受版本上递增改造，每次必须以完整真实任务同时验证预期增益与既有 M0 能力退化；有效才提交并打版本标签，无效则回退。它覆盖旧 R1–R7 在 M0 之后的组件筛选顺序，但不改变研究问题、创新 A–D、无 checker 边界、数据划分或 final holdout 禁令。
- 最终方法运行规范：`method_discovery/docs/FINAL_METHOD_OPERATIONAL_NORTH_STAR_20260824.md`。该文件定义最终 best-paper 产物从任务初始化、持续静默、注意激活、主动重建、判断、干预、持续 repair、局部释放、根任务完成到非成功终止和事后归档的完整生命周期。M1–M7 的实现和验收必须反向覆盖该规范；机制文件存在不等于方法完成。该规范固定目标行为而不固定唯一 schema、图实现、prompt 或数学估计器，允许在阶段目标不漂移、真实任务留痕和防过拟合约束下进行多轮实现尝试。
- 成本贯穿而非延后：从 M1 起每次真实运行都必须记录 Agent/monitor 调用、输入输出与可见 token、延迟、wall time 和可得美元成本；同等效果下前期即优先简单、低成本实现。若增益只来自更多计算、出现异常成本或明显能力—成本冲突，必须按结果停止点汇报。M6 是在可靠能力成立后的系统性降本、active-view 和严格等预算验证阶段，不意味着 M1–M5 可以忽略成本，也不授权在能力成立前以降本为由削弱监察能力。
- M1-C 成本门禁：`method_discovery/docs/M1_ACTIVE_RECONSTRUCTION_COST_GATE_20260825.md`。M1-C 以“最小被动唤醒视图 + 同一监察者主动重建”修复旧实现重复发送历史边界 prompt、完整状态视图并同时保留主动工具的异常成本：外部系统可靠保存原任务、ledger、repair episode、语义状态和完整归档；被动输入承担态势唤醒与导航；监察者自主决定查看什么和查看多少。2026-08-26 用户裁决停止继续打磨 M1，回退到 commit `6128acc` 的 M1-C 能力—成本折中并将其冻结为 M2 的工程父版本；后续 sparse wake 与 bounded-UNKNOWN 候选保存在 rejected 历史分支，不进入 M2。系统性等预算降本仍属于 M6。

### 已确认的研究问题

第一篇论文研究长程 Agent 任务状态的两类关键失真：

1. 未来仍需使用的 obligation、constraint、termination condition 或事实没有进入或没有保留在后续状态中，即 representation omission；
2. obligation 仍被保留，但 Agent 使用不足或不等价的代理证据将其错误标记为完成，即 unsupported closure / completion-evidence drift。

目标是维护能够统一处理表示遗漏和错误闭合的可修订任务状态，并根据偏移类型采取合适的恢复动作。不得擅自把论文主问题替换成宽泛的 memory retrieval、PMA 升级、单纯提醒时机、纯 completion checker 或 benchmark 构建。

### 已确认的创新候选

- 创新 A：Dual-Layer Evidence-Carrying Task State。声明式任务状态是核心；过程控制状态作为待 R1 判别的第二层，必须证明独立增益，否则降级为按需 active view。
- 创新 B：Challenge-Guided Versioned State Revision。其已验证核心仍是由公开可见变更/冲突驱动版本推进、保留旧证据并防止同版本证据洗白；challenge–response–residual repair loop 是待 R4 验证的过程扩展；acceptance-predicate 扩展仍是可弃权候选。
- 创新 C：Evidence-Gated Decision Boundaries。Completion Kernel 是核心候选；local/global completion boundary 与 high-risk transition boundary 必须分别消融，不能因叙事完整直接纳入。
- 创新 D：Budgeted Deliberative Recovery Controller。保留 typed recovery actions，并候选性加入事件触发、query-conditioned active view 和有界 repair loop。

当前保留 F0 state only、F1 boundary gated、F2 event-triggered one-shot 和 F3 deliberative closed-loop 四个候选族。最终组合必须由 R7 的最小有效组合决定。P4 risk-triggered re-observation 是动态环境扩展；`use_now`、`access_risk` 和 budgeted active view 属于恢复动作选择层，不得替代 A–C 的主问题。

默认架构只有一个具有持续身份的监察者。连续认知由外部可审计的 declarative/procedural state、事件归档、版本历史和 active view 保证，不依赖模型调用之间不可见的隐式记忆。低成本 L0 是确定性归档、索引、delta 和同一状态的增量维护；关键事件才触发同一监察者的较深审议。不得默认拆成“小模型维护、强模型判断”并把跨模型传递损失引入核心方法。

### 并发监察执行硬约束（2026-08-28 用户纠偏）

- 任务 Agent 是默认持续推进的执行主体；监察者必须作为并发观察者消费公开事件、主动检索工作区并维护状态，不得把每轮监察模型调用放进任务 Agent 的同步关键路径。
- `SILENT` 表示没有用户式输入，不能要求任务 Agent 停下来等待一个 SILENT 判断。严禁恢复“每个工具边界暂停 → 同步调用监察者 → 返回后才能继续”的逐轮审批架构。
- 监察者只有形成有证据依据的真实纠偏时，才通过高优先级干预队列模拟用户输入；任务 Agent 在下一安全可中断点、下一次模型推理之前消费该输入。危险且可取消的尚未执行动作可以阻止；普通正在执行的工具不得被不安全地中途破坏。
- 监察者可在后台持续跟踪 repair episode、读取增量轨迹、测试、diff 和产物；这些调查及其 API 延迟、超时、崩溃或重启均不得冻结任务 Agent。监察故障必须被显式记录，不能伪装成正常 SILENT，也不能凭故障生成 HOLD。
- 主动监察不得被实现成异步 packet reviewer：任务侧只允许把公开事实追加到可检索事件归档，并发出不含语义内容的游标/唤醒信号；不得把每个完整 packet 自动塞给监察模型。监察者必须拥有自己的观察游标和循环，自主决定何时查询增量轨迹、测试、diff、文件与历史、看多少以及何时重新静默。
- 根任务完成提议可以作为独立的高风险边界接受明确的完成控制，但不得由此把普通执行边界重新串行化。最终方法必须分别报告普通并发监察延迟与完成边界控制成本。
- 本约束来自真实 M3-B Fyne 2.2 运行暴露的架构偏移：同步 `checkpoint_callback -> monitor.review()` 使一次中转 SSE 卡流冻结整道任务。后续任何实现、重构和实验预检必须有自动测试证明“监察永久阻塞时任务仍推进、形成干预时可在下一安全边界送达”。

### 无 Checker 边界

- 核心部署方法不得假设可靠在线 checker、gold answer、隐藏测试结果或 native verifier。
- 在线只允许使用公开任务要求、Agent 动作和声明、工具调用与结果、普通环境观察以及已维护的状态历史。
- Agent 自述只能构成 claimed；普通观察可构成 observed；局部支持可构成 supported；冲突、未知、过期和替代必须分别保存为 contested、unknown、superseded 等状态。
- 证据不足时必须保留 UNKNOWN，不能虚构完成。
- native verifier 只用于任务结束后的效果评价、oracle upper bound 或研发期反例分析，不得泄漏到同一次部署运行。
- Stage 5 的 obligation/version/provenance/completion-boundary/telemetry 是可重用 substrate；independent-checker-only closure 和 `PublicCommandChecker` 只属于 oracle/诊断路径。

### 方法发现顺序

已完成 Stage 1–4.5 基础设施和基线；Stage 5 substrate 保留；Stage 6C 的版本化修订核心结果保留，不重复包装为新实验。2026-08-22 起，先执行 M0 人工能力上界阶段；旧 R1–R7 保留为 M0 成立后按真实失败驱动调用的机制目录，不再要求在 M0 前逐组件筛选。当前顺序为：

1. R0：多来源偏移事件、真实任务协议和 held-out 划分冻结（已完成）；
2. M0.1--M0.4：人工能力上界重建、在线循环和真实任务确认（已完成核心能力构建）；
3. M0-F：冻结 `m0-v1`，修复 timeout/JSON 归档等不改变策略的实验基础设施（已完成，`m0-v1.1`；首个 M1 长任务继续确认两小时外层限制）；
4. M1：已按用户 2026-08-26 的阶段收束裁决冻结。M2 的父版本为 `6128acc` 的 M1-C 主动重建实现加行为中性的测试契约修复；这表示方法发现进入下一增量，不得夸大为已完成正式论文级充分验证；
5. M2：已于 2026-08-28 收束。共同真实任务筛选保留 M2-C 的 scoped semantic-impact revision；M2-D 的直接依赖失效通道在 101 个监察边界内触发 0 次且运行超时，未证明相对 C 的独立收益，因此回退 D 并冻结 `m2-c-structural-gate`；详见 `method_discovery/docs/M2_STAGE_CLOSE_AND_M3_ENTRY_20260828.md`；
6. M3：当前阶段。以冻结的 M2-C 为父版本增加 decision-centered epistemic control，解决调查范围、证据获取价值与停止问题。普通监察采用正交的可选 `intervention_message` 与 `patrol|focused` 注意模式，不得恢复 HOLD/SILENT/RELEASE 串行动作协议；根 completion 独立使用 `allow_complete|continue_task`；
7. M4：形式化证据门控边界、typed recovery 和持续 repair/release；
8. M5：对单一累计方法做可靠性稳定、回滚消融和跨来源复验；
9. M6：汇总 M1–M5 持续记录的成本证据，在不预设成功的前提下进行系统性 capability-preserving cost reduction、active view 和等预算验证；
10. M7：未见真实任务、等预算消融与最终最小方法冻结；
11. Stage 7：冻结后运行多来源正式实验与论文证据。

M3 当前按 `M3.1 基础感知 -> M3.2 自适应观察节奏 -> M3.3 连续语义片段必要性审计（已否决持久实现） ->
M3.4 自主工具循环能力审计与异步干预协议重构 -> M3.5 跨轮次连续认知` 递增弥补人工监察差距。每一项完成后必须
停止汇报，不得自动进入下一项。每个实现或验证步骤开始前，必须带着该步骤的具体目标重新
读取对应的真实人工监察轨迹、当时可见上下文和实际决策，先形成证据锚点再修改；不得凭印象
或合理化猜测复刻人工策略。当前细化计划与证据门禁见
`method_discovery/docs/M3_HUMAN_GAP_INCREMENTAL_PLAN_20260829.md`。

M3.5 当前工程实现以
`method_discovery/docs/M35_R5_MODEL_OWNED_SEMANTIC_FILES_20260831.md` 为准：稳定 system
context、同一监察者持续 history、模型自主管理的自然语言 `state/`/`evidence/` 文件和通用原子
读写工具共同提供连续认知；运行时只保证安全、并发、版本和原子性，不再要求模型维护 obligation
ID、`workspace_delta` 或旧 M1/M2/M3.2/M3.5 开关。该实现尚未获得完整真实任务效果验收，不得据
工程测试声明 M3.5 候选已接受或冻结。

2026-09-01 用户确认进入 clean Monitor Agent foundation reset。当前实现顺序以
`method_discovery/docs/C1_CLEAN_MONITOR_AGENT_FOUNDATION_SPEC_20260901.md` 为最高优先级工程规格：
GenericAgent 只提供 provider session、Agent/tool loop、通用代码执行、history/log/telemetry 和 abort
等可复用运行原语；新 Monitor Agent 仍是独立研究产物，拥有自己的身份、权限、观察、记忆和控制
机制。旧 M0--M3.5 实现保留为行为证据与回归对照，不再作为继续叠加兼容逻辑的代码母体。先完成
C2 独立 Monitor Agent 内核，再完成 C3 并发观察与强制纠偏闭环，之后才允许进入 wiki/非线性语义
记忆、证据修订和成本机制发现。该重置不改变研究问题、创新 A--D、无 checker 边界、真实任务门禁
或旧阶段结果；两层任务观察固定为“逐轮公开 synopsis + 原始公开证据”，不得新增确定性语义中间层。

2026-08-29 用户进一步裁决：M3.1--M3.5 期间不逐项运行完整真实任务。每项只允许通过代码
回归、确定性集成检查和既有人工轨迹对齐来确认“工程实现完成”，不得据此声明效果成立、接受
候选或冻结版本。必须保留逐项独立开关、决策理由和归档，以便累计完成 M3.5 后统一运行真实
任务并追溯消融。M3.5 完成后首次累计真实运行仍适用独立启动门禁，未经用户确认不得执行。

R0 同时冻结事件级诊断集与 Final120 真实任务协议。离线事件、静态 JSON、轨迹重放、schema 有效率和 LLM judge 只属于工程验证或候选生成，没有核心方法晋级权和淘汰权。M1–M7 的版本接受必须主要依据 `method_discovery/r0_real_tasks/protocol.json` 规定的完整真实 GenericAgent 分支；不得用压缩 packet、模拟事件或模块分数替代真实任务。`final_holdout` 在方法冻结前不得运行 treatment 或用于方法选择。

旧 R1 已由 M0-v1 的真实任务能力证据完成其“先建立不受复杂 schema 约束的直接监察者母体”使命，不再重复筛选 B1。旧 R2–R6 的机制门禁继续作为 M1–M6 的验收约束：M1 只能根据 M0 的真实失败加入最小外部语义锚点，并验证连续更新中的信息存活、错误闭合、冲突重开、污染累积和成本；M2–M3 必须允许 UNKNOWN、区分“未观察到”与“未发生”，并测量错误 warrant/错误阻断；M4 必须与一次性提醒比较，并以 Agent 后续行为而非口头接受判定 uptake；revision、dependency 和各类 gate 必须独立开关，不得一次堆叠；M6 必须验证 query/use-site-conditioned active view，并与静态截断、完整 ledger/history、PMA-style reminder、always-visible state 和等频随机选择做严格等可见 token/call/cost 比较。小模型维护只作为附加消融，主实验默认同一监察者模型。

方法发现采用 M0-v1 起步的单一递增版本线，不采用逐阶段孤立模块冠军串联，也不并行维护无界候选束。每次只在上一接受版本上增加一个服务于最终目标的相干机制；完整真实任务同时裁决预期增益与既有 M0 能力退化。研究实现不是确定流程：同一机制目标内允许根据真实失败进行多轮实现尝试，但每次必须记录假设、改动、任务、预算和结果，并轮换任务防止单题过拟合；出现可解释结果、预注册预算耗尽、重大设计选择或应当放弃/回退的证据时必须停止汇报。M5 才检查累计机制的必要性与少量关键交互，M7 才按未见真实任务、等预算和消融冻结最小有效组合。

同一阶段内用于选择同类候选的首轮判别实验必须固定在同一道完整真实任务上，并保持任务版本、任务 Agent、监察模型、turn/time 上限、在线信息边界和可用预算一致；不得为不同候选临时更换题目后直接横向比较。只有在该共同任务上形成可比的候选结果、选出暂定优胜者后，才能轮换其他 `method_dev` 任务检查泛化和单题过拟合。若共同任务因镜像、环境或评价故障不可运行，必须先报告并由用户决定统一换题，不能只为某个候选单独换题。当前 M2-A/B/C/D 候选筛选的共同任务固定为 Fyne 2.2（注册表规范 ID：`roadmapbench:fyn-2.2.0-roadmap`）；已有异题运行只作为候选诊断证据，不作为严格横向比较结果。

每层必须可单独关闭并通过判别实验。不得在状态表示尚未成立时同时堆叠提醒、触发、完成控制和主动再观察；不得因为叙事完整而保留无独立增益的组件。

### 防漂移检查

每次开始新的方法开发阶段前，必须复核：

1. 当前改动服务于创新 A–D 中哪一项；
2. 是否错误引入在线 checker 或隐藏评价信息；
3. 是否把 PMA 基线误当成研究母体，或退化为仅增加字段/改 prompt；
4. 是否改变已确认研究问题、创新声明或阶段顺序；若改变，必须先停下请求用户决策；
5. 是否仍以严格实验支持的最小有效组合为收敛目标。

删除条件：只有方法发现阶段完成、最终算法与消融结论冻结后，才能在用户明确确认下删除本临时节；删除时应把最终稳定约束迁移到正式研究规格，而不是直接丢失。

本文件适用于 `E:\LongContext` 下的研究与开发工作。子目录若存在更具体的 `AGENTS.md`，应同时遵守；发生冲突时，以作用域更具体的文件为准，并向用户说明冲突。

## 1. 总体原则

- 开发工作必须采用“目标 → 阶段 → 步骤”的分层规划，不直接把一个大型研究或工程目标作为单次实现任务。
- “方法发现”“实验基础设施建设”“完整实验运行”“论文实验整理”等均视为大型目标，必须拆成多个可独立验收的阶段。
- 每个阶段应有明确的目标、范围、交付物、测试方法、完成条件和停止点。
- 每个阶段内部继续拆成有序步骤；每一步只完成一个清楚、可验证的改动目的。
- 优先实现能够证伪假设的最小改动，不在同一步中堆叠多个尚未验证的研究机制。

## 2. 开始开发前的规划要求

任何非微小开发任务开始前，必须先向用户给出计划，至少包含：

1. 本轮大型目标；
2. 阶段划分及顺序；
3. 当前准备实施的阶段；
4. 当前阶段的逐步实现计划；
5. 预计涉及的文件或模块；
6. 每一步的验证方式；
7. 需要用户决策或未来确认的门禁点。

未经用户确认，不得一次性实施整个大型目标。用户确认当前阶段后，只获得当前阶段的实施授权，不自动获得后续阶段授权。

若开发过程中发现原计划依赖错误、范围明显变化或需要新增重大组件，应停止实施，更新计划并请求用户确认。

## 3. 阶段门禁与用户确认

- 2026-09-12 用户要求每个阶段验收后进行一次独立 Git 提交，报告 commit 与文件范围，便于定位回归。仅提交本阶段核查过的文件，不混入其他未提交代码、密钥或运行垃圾；历史积压不可伪装成当前阶段新增。保存版本不等于认可方法有效，也不自动授权下一次真实启动。

- 每完成一个阶段，必须停止，不得自动进入下一阶段。
- 任何完整真实任务运行都设有独立的启动门禁。即使用户已经确认当前开发阶段、候选机制或实验规划，仍不得据此自动启动真实任务。每次启动前必须停下来报告任务 ID、condition、任务 Agent 与监察模型、turn/time 预算、预计 API/时间成本、对照依据和本次判别目标；只有用户针对该次真实启动明确确认后才能执行。预检、manifest 生成或上一条真实分支的授权均不自动授权下一条分支。
- 阶段完成后必须向用户报告：
  - 本阶段完成了什么；
  - 实际改动了哪些文件；
  - 每个文件的关键改动；
  - 使用了哪些测试、检查或实验；
  - 测试结果和原始产物路径；
  - 与阶段完成条件逐项对照的验收结果；
  - 已知限制、失败、意外结果和未解决问题；
  - 下一阶段建议，但不得直接开始。
- 只有用户明确确认后，才能进入下一阶段。
- 若阶段结果本身会影响后续方法选择，例如某个baseline已经足够、某项机制没有增益、成本异常或出现反例，也必须停下来展示结果并等待用户决定。

## 4. 单步改动规模限制

- 每个实现步骤的代码改动量不得超过 600 行。
- 这里的“代码改动量”默认按该步骤相对开始时的 diff 计算，新增行与删除行之和均计入；测试代码、配置和脚本也计入。
- 纯机械生成的实验结果、日志、锁文件和数据表不计入代码行限制，但必须单独说明来源和生成方式，不得借生成文件绕过代码拆分要求。
- 文档改动原则上不计入“代码改动量”，但大型文档也应按主题拆分，避免一次混入多个阶段结论。
- 如果一个不可分割的安全迁移或生成改动预计超过 600 行，必须在修改前停止，说明原因、替代拆分方案和风险，并由用户决定是否例外。
- 不得通过压缩代码、合并多条语句、删除可读性内容或其他形式规避 600 行限制。

## 5. 决策升级规则

遇到以下情况时必须停止并请求用户决策，不得自行选择：

- 两个或多个方案会实质改变研究问题、创新声明或论文定位；
- 需要扩大实验范围、显著增加API/token/时间/算力成本；
- 需要采用不可逆、破坏性或会覆盖重要历史产物的操作；
- 需要更换主要模型、benchmark、verifier、评价指标或公平比较协议；
- 发现当前实现与用户已确认的方法假设冲突；
- 结果支持放弃、降级或替换某个核心创新；
- 无法根据现有证据判断某项机制应如何实现，且不同选择会影响实验结论；
- 需要用户提供API、密钥、外部服务、人工标注或其他新权限。

可以自行决定的内容限于不改变已确认研究范围的局部、可逆工程细节，例如内部命名、小型重构、测试夹具和明显的错误修复。仍应在阶段报告中说明。

## 6. 结果查看与提前停止点

以下结果一旦出现，应在继续扩展实现前停下来向用户展示：

- 第一批真实任务的baseline结果；
- 新组件首次产生可测提升或明显退化；
- 关键消融显示某组件没有独立贡献；
- 方法只因额外模型调用、token或运行时间而提升；
- native verifier与代理指标结论不一致；
- 出现高价值反例、严重false blocking、状态污染或无限验证；
- 实验结果足以在多个候选方法组合之间做选择；
- 结果会改变下一阶段实现顺序或论文贡献结构。

报告结果时必须区分事实、推断和待验证假设，不用少量成功案例代替整体结论。

## 7. 测试和证据要求

- 每一步改动都必须有与风险相称的验证，不能只依赖代码阅读或Agent自述。
- 优先依次使用：单元测试、集成测试、确定性fixture、原生verifier、小规模真实任务、扩大规模实验。
- 研究方法实验必须保存baseline、treatment、配置、模型、预算、随机性设置、日志、状态变化、最终产物和verifier结果。
- 比较方法时应保证除目标机制外的其他条件尽量一致，并报告token、调用次数、延迟和可用时的美元成本。
- 阶段不能因为“代码已写完”而完成；只有其完成条件有测试或产物证明时才算完成。
- 测试失败时不得静默降低验收标准。应报告失败并判断是实现错误、环境问题、任务能力问题还是研究假设未成立。

### Docker/Harbor 真实任务恢复 SOP

- 本机 Docker Desktop 固定安装在 `E:\Docker\Desktop`；标准批次只要求 Linux Engine 常驻，任务运行期间只使用 Docker CLI/API，不逐题启停 Desktop。
- 启动前先运行 `docker info --format '{{.ServerVersion}}'`。成功才进入镜像、manifest 和任务预检；不得只根据 `Docker Desktop` 进程存在判断 Engine 可用。
- Engine 未运行时，优先直接启动 `E:\Docker\Desktop\Docker Desktop.exe` 并等待 `docker info` 成功。首次启动允许出现 Dashboard；Engine 就绪后可关闭窗口而不停止 Engine。不要在受限 Codex shell 中使用 `docker desktop start/restart/stop`：该子命令会写 `C:\Users\hsy\AppData\Local\Docker\log\host`，可能因沙箱权限失败并扰动本来可恢复的 Desktop 会话。
- `permission denied`、named-pipe 不可达或空 ServerVersion 时，先区分三种情况：Desktop 未启动、Desktop 已启动但 Engine 尚在初始化、当前 shell 对 Desktop 日志/pipe 的权限受限。检查 `docker desktop status` 只作诊断，不以其代替 `docker info`；不得连续混用 GUI 启动、CLI restart 和多进程重复启动。
- 启动后采用短轮询等待 Engine，单次等待不超过 60 秒并向用户更新；Engine 就绪后立即复用，不再重启。若当前沙箱确实不能访问 pipe，应保留 `prepared_not_executed` manifest 和零 API 污染事实，但在得出阻塞结论前必须完成上述固定路径启动与等待流程。
- Engine 就绪后按 `long_context_bench/docs/DOCKER_HARBOR_REAL_TASK_SOP.md` 执行镜像身份、已有容器、磁盘、API、源码摘要和 run-id 预检。每题结束只清理该题容器/镜像策略指定的资源，不停止整个 Engine。

## 8. 方法发现阶段的特别要求

- 方法发现必须采用递增实现和判别实验，不一次实现所有候选创新。
- 推荐顺序为：实验基础设施 → baseline → 最小候选组件 → 组件消融 → 组合方法 → 扩大实验。
- 每加入一个研究组件，必须能够单独关闭，并保留明确的配置或代码路径用于消融。
- 最终方法应由严格实验支持的最小有效组合决定，而不是按模块数量或叙事完整性决定。
- 如果简单baseline与复杂方法效果相当，应优先接受简单结论并停止无依据扩展。
- 离线轨迹分析、代理指标和LLM自评分不能替代真实分支运行与原生verifier结果。

## 9. 推荐的阶段报告模板

```text
阶段名称：
阶段目标：

完成内容：
- ...

文件改动：
- path: 关键改动

验证：
- command/test/experiment
- result
- artifact path

完成条件核对：
- [x] ...
- [ ] ...

限制和异常：
- ...

需要用户确认或决策：
- ...

下一阶段建议：
- ...
```

阶段报告发出后停止工作，等待用户明确确认。
