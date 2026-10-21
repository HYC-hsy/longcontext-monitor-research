# RJC-v0：回执证成的缺口关闭（Receipt-Justified Closure）设计

日期：2026-10-21。状态：设计稿，未实现、未调用模型、未运行任务。
基线身份：仓库 HYC-hsy/longcontext-monitor-research，分支 crs-v0-20261007，HEAD f1ee46d00736944b6467cd000bdb5c92ae7cc6be。
本目录是新增目录，不修改既有文件。`offline_replay/` 中是本设计依据的零模型重放脚本与输出。

## 0. 一段话

Task、PoS、PMA 三方都用自然语言判断"某个要求是否已经满足"，而在三次 SQLite 运行里，唯一与官方结果一致的信号是工具回执本身。RJC-v0 只做一件事：把"关闭一个缺口或一条失败记录"变成必须引用回执的动作。程序保证三条可机械检查的不变量：失败记录只能被更晚的回执关闭；每次关闭都留下"失败回执 对 关闭回执"的配对；Task 宣布完成前，所有仍开放的缺口与配对必须被逐条过目一次。语义判断仍由模型做，RJC 不新增裁判，不新增模型角色，不改 PMA 核心。它是 PoS 的结构化缺口加 PMA 的"只在可能改变下一步时介入"思想，在同一条可追溯的回执链上重组。

## 1. 问题与证据

### 1.1 三次 SQLite 运行的终态事实

| 运行 | 方法 | 命令可用性验证方式 | PoS 完成时缺口 | 官方 reward |
|---|---|---|---|---|
| pos-bcb35740 | PoS-only | 符号链接到 /usr/local/bin，新进程 `which` 成功 | 空 | 1 |
| pos-41c50c | shared_view 旧轮 | 同一脚本内 export 后 `which` 成功；从未出现失败回执 | 空（被错误清除） | 0 |
| pos-68764e | shared_view 新轮 | 第 13、14 步 `sqlite3: command not found`；第 15 步 login shell 验证 | 两条 achievement 加一条 epistemic，stale | 0 |

官方测试在非 login 的 Python 进程里用 `shutil.which` 查找，三项全部失败于找不到 sqlite3。

### 1.2 辅助模型如何把失败回执"解释掉"

pos-68764e 中 PMA 在 Step 15 的 Phase 1 看见了 command not found 和 PoS 的 PATH 缺口，输出"PATH issue is a red herring"，并把"二进制在标准 bin 位置即满足 available in PATH"保存为 procedural 记忆；Step 16 Phase 2 据此 no_intervention。PoS 一侧，Sentinel 从 step 8 后连续拒绝或 unusable，保留了含 PATH 缺口的旧状态并标 stale。Task 最终用 login shell 验证成功，回复声称"任意 shell 可用"，GA 因回复无工具调用走默认放行。

三方各自出错，方向不同：PoS 保留了正确缺口但无人问；PMA 用解释关闭了失败；Task 用局部验证扩大结论。这不是信息缺失，所有材料都在输入里。

### 1.3 零模型重放（`offline_replay/failure_ledger_replay.py`）

规则：exit 非零或有失败行的 code_run 回执开一条失败记录，记录失败命令词；只有更晚、exit 0、无失败行、且在命令位置调用同一命令词的 code_run 回执能关闭它；模型文本不能关闭。目标相关性由任务原文词与命令词的包含关系标记。

| 运行 | 失败记录 | 完成时开放 | 完成时开放且目标相关 | 关键配对 |
|---|---|---|---|---|
| pos-68764e | 5 | F3（`file` 缺失，无关） | 0 | F4/F5 `sqlite3: command not found`（失败调用行 `which sqlite3`、`sqlite3 --version`）被第 15 回合回执关闭，关闭调用行 `bash -l -c 'which sqlite3 && sqlite3 --version'` 与 `/app/sqlite/bin/sqlite3 --version` |
| pos-41c50c | 5 | F5（`file`） | 0 | 无 sqlite3 失败；gcc/gcov/make 安装期失败 F3/F4 目标相关，均被后续回执关闭 |
| pos-bcb35740 | 4 | F4（`file`） | 0 | 无目标相关失败 |

阶段 1 后以生产账本重放（`offline_replay/replay_with_ledger.py`，输出 `ledger_report_v0.json`）复核了上表；设计期的探索脚本 `replay_invariants.py` 保留作记录。

两个结论。第一，机械规则本身拦不住 SQLite：login shell 回执在机械上合法地关闭了 PATH 失败。第二，机械规则能把"失败脚本"和"关闭脚本"配成一对放到判断者面前，而当前任何一方都看不到这个配对。另外，`file` 工具缺失在三次运行中都开放到最后，说明完成复核的触发必须用目标相关性过滤，否则正确运行也会被打扰。

### 1.4 文献中的同一现象

- Overclaiming propensity（arXiv 2609.20812）：前沿 agent 系统性地把最终回复与上下文中的证据矛盾地写成完成。
- Long-Horizon-Terminal-Bench（arXiv 2607.08964）：false-finish 模式，agent 高估完成并少投入最终验证。
- LongHorizon-Harness（arXiv 2608.01964）：执行者的完成声明不直接改状态，记录只在有干净审计证据时标为 completed。
- Evidence-Carrying Termination（arXiv 2608.23623）：只有当类型化证书把每条必需声明绑定到有效的轨迹证据时才允许 complete；验证是确定性的，失败一律返回 continue。

## 2. 从两个方法各借什么，精确到代码

### 2.1 从 PoS 借

| 借什么 | 位置 | 在 RJC 中的用途 |
|---|---|---|
| 结构化缺口 EpistemicGap/AchievementGap(target, reason) | vendor/belief/beliefStates.py | 完成复核的枚举对象；关闭审核的对象 |
| 缺口身份稳定化 `_stabilize_gap_targets` | vendor/belief/manager.py | 跨步追踪同一缺口何时被移除 |
| 候选 → Sentinel 审核 → 采纳或保留 | manager._validate_candidate | 关闭审核挂在这里，不改采纳规则 |
| 审核输入追加 system 消息的方式 | shared_view.SharedViewSentinel._request_json | 以同样方式追加 closure_review，不改 vendor |
| 面板 `shared_panel` 与 `_required_state` | shared_view.py / candidate.py | 展示失败账本 |
| 论文：Sentinel 区分内部与外部不一致 | PoS 论文 §3.2 | RJC 新增第三类：关闭无证成。PoS 消融显示去掉一致性验证在 ALFWorld 降 14.93 分，说明审核这一层值得加强而非绕过 |

### 2.2 从 PMA 借

| 借什么 | 位置 | 在 RJC 中的用途 |
|---|---|---|
| 关心的内容类别：要求、环境事实、尝试、失败诊断、有效做法 | PMA 论文 §1、§3 | 失败记录就是"失败尝试"这一类的机械化版本 |
| 只在可能改变下一步时介入，否则沉默 | PMA 论文 §4.3 消融：选择性介入 macro 64.3，always inject 63.5，full-bank 61.5 | 完成复核只触发一次、只在有开放项时触发 |
| 两阶段：先整理再决定 | memory/universal_memory | 账本在 PoS 更新前整理，复核在完成边界决定 |
| 已有部件：Phase 1 操作与来源映射 `entry_sources` | memory_adapter.py | 给记忆条目打"创建时存在开放失败"标签，不改 PMA 核心 |

### 2.3 从本仓库既有部件借

- 提交 B 的 evidence_id 绑定（beliefSentinel.py 55e2a74d）：关闭审核要求引用 evidence_id 加短引文，复用其校验。
- GA 完成门钩子：agent_loop.py 第 304 到 332 行构造 CompletionProposal 并调用 decide_completion；第 375 到 377 行在 no_tool 分支把非 ALLOW 决策转成 next_prompt 继续。这是程序保证的不可绕过路径。shared_view 当前没有设置 handler.completion_gate，走 DEFAULT_ALLOW。
- CRS 的"先提议、下一轮才放行"两回合（runs/crs_v0_20261007）。

## 3. 理论锚点与明确不声称的东西

Doyle 1979 的证成式真值维护（JTMS）：一个节点只有在至少一条有效 justification 支持时才 IN；justification 失效则节点 OUT；nogood 记录不能同时成立的集合。映射：缺口"已关闭"是一个节点，它的 justification 只能是回执；失败回执是对"用文本关闭"的 nogood。这给出的是数据结构与不变量，不是任何最优性。

LongHorizon-Harness 的原则"状态只用环境独立验证的事实更新，执行者声明不改状态"与 ECT 的"验证器确定性、失败即 continue、soundness 相对于合同与账本"是 RJC 的工程先例。RJC 对应的可声称性质只有一条，与 ECT 同样是相对的：若账本如实记录回执，则每条被标为已关闭的失败记录都存在一条更晚的、满足机械条件的回执，且每次完成放行之前每条开放项都被 Task 显式处理过一次。它不保证关闭在语义上充分，不保证外部真实。

不声称：POMDP 最优控制、Dempster-Shafer 组合、Safety/Progress/Completeness 定理。真实 task_state 在线不可观察，不作 oracle。

## 4. 不变量与各自能做什么

| 编号 | 不变量 | 机械还是模型 | 对 SQLite 失败链的作用 |
|---|---|---|---|
| I1 | 失败记录只能被更晚的 code_run 回执关闭；PoS 缺口移除、PMA 记忆写入、Task 文本都不能关闭 | 机械 | 阻止 PMA 的 red herring 写入把 F4/F5 变成"已解决"；账本在 Step 15 仍显示开放，直到第 15 步回执 |
| I2 | 每次关闭保存配对：失败回执脚本、失败行、关闭回执脚本、关闭回执 stdout 头部 | 机械 | 把 `sqlite3` 失败与 `bash -l -c` 关闭并列给 Sentinel、PMA Phase 2 和 Task |
| I3 | Task 完成提议时，若 PoS 最后采纳状态有开放缺口，或存在目标相关的开放失败记录，则恰好一次 CONTINUE，附结构化清单；第二次提议放行 | 机械触发，模型作答 | pos-68764e 触发（三条缺口）；bcb35 与 41c50 不触发 |
| I4 | 候选移除缺口时，审核输入附带被移除缺口、当时开放或刚关闭的配对，并要求对每条移除引用 evidence_id | 机械构造，模型判断 | 若 PoS 有一天接受"PATH 已满足"，Sentinel 会看到关闭配对而不是只看候选 |
| I5 | PMA 条目创建时若存在目标相关开放失败记录，shared selection 渲染中带机械标签 | 机械 | Step 14、15 写入的两条 procedural 记忆会带"写入时 F4/F5 开放"标签 |

I3 是唯一改变 Task 行为路径的部分，也是唯一真正需要实验检验的部分。I1、I2、I5 是记账，I4 是审核输入。

## 5. 数据结构

```
FailureRecord
  failure_id        F<n>，episode 内递增
  turn, receipt_id  开记录的 GA 回合与 tool_use_id
  exit_code         回执 exit_code
  tokens            失败命令词（从失败行解析；无失败行时取脚本命令位置词）
  fail_lines        至多 3 行失败行原文
  goal_relevant     与 PoS goal.user_input 词的包含关系
  closed_by         null 或 {turn, receipt_id, tokens, closing_script_sha256, stdout_head}

ClosureReview（审核输入附件）
  removed_gaps      before 有、candidate 无的缺口 target 列表
  open_failures     当前开放且目标相关的 FailureRecord
  recent_closures   自上次采纳以来新形成的配对
  instruction       "每条移除需引用 evidence_id 与短引文；无引用的移除记为 unsupported_closure"

CompletionReview（完成复核清单）
  open_gaps         PoS 最后采纳状态的 achievement 与 epistemic 缺口，带 stale 标记
  open_failures     目标相关开放记录
  closures          目标相关的关闭配对
  prompt            要求 Task 对每条：引用一个 tool_use_id 作为关闭依据，或执行新动作，或显式标记未解决
```

所有列表有字符上限，超出部分计数并标注，不静默截断原始回执。

## 6. 接线点

### 6.1 不改停着的版本

阶段 1 实现时的修订：不复制 complement 文件。新目录 method_discovery/rjc_v0_20261021/ 中的 rjc_view.py 通过 sys.path 导入 pos_pma_complement_v1_20261019 的 SharedViewSentinel、SharedViewBeliefManager、SharedViewEpisode 并以子类扩展，开发线程对 shared_view 的后续补修自动继承，diff 更小。新增 failure_ledger.py。阶段 2 接 worker 时，staging 需要同时拷贝 complement 文件与 rjc 文件到 pos_runtime，并让 worker 按候选名 pos_pma_rjc_v0 加载 rjc_view。

候选名需要新身份 pos_pma_rjc_v0，否则与 pos_pma_shared_view_v1 的源码绑定哈希混淆。这要求 worker.py、single_run.py、live_launcher.py 的白名单各加一行。为不碰停着的 worktree，建议在新路径建新 worktree 与分支，所有改动在那里进行。

### 6.2 五个接入点

1. 账本更新：SharedViewEpisode.update 已接收 source_events（含 result.exit_code、stdout、stderr）与 action_batch（含 arguments.script）。在 PoS 更新前调用 ledger.ingest，记录在 episode.events 与 get_result。
2. 审核输入：SharedViewBeliefManager._validate_candidate 前计算 removed_gaps，写入 sentinel.closure_review；SharedViewSentinel._request_json 在 consistency lane 追加一条 system 消息，方式同既有 shared_audit_history_input。vendor 不改。
3. 面板：shared_panel 增加 failure_ledger 段，仅目标相关开放记录与最近配对，字符有上限。
4. 记忆标签：SharedViewEpisode._bind_selection 在 source_mappings 旁加 written_while_open_failures。PMA 核心、提示、触发不变。
5. 完成复核：GA agent_loop 在 complement 分支创建 pos 后，受 GA_POS_COMPLETION_REVIEW=1 保护，设置 handler.completion_gate = PoSCompletionReviewGate(pos)。gate 调用 pos.exchange('completion_review', turn=...)，worker 新增该命令分支，episode.completion_review 返回 CompletionReview。首次返回 CONTINUE 加 next_prompt，第二次返回 ALLOW_COMPLETE。异常走既有 ERROR_FAIL_OPEN。这是对 GA 的唯一改动，约 15 行，加 worker 一个分支。

### 6.3 并发与边界

只有根完成边界同步等待，符合 AGENTS.md 对完成边界的例外；普通步骤不新增同步调用。复核提示只使用原任务原文、PoS 缺口文本、回执原文，不含隐藏评价信息。

## 7. 成本

零新增模型角色。每个 episode 最多新增一次 Task 回合。Sentinel 输入增量上限 2000 字符，面板增量上限 2000 字符。相比当前 shared_view 的 66 次 PoS 加 36 次 PMA 调用，RJC 的增量是一次 Task 调用与少量 token。

## 8. 实验与证伪

### L0 零模型重放（已完成，见 §1.3）

### L1 固定上下文复核回合重放（需模型调用授权）

对 pos-68764e 的最终回合，用同一上下文追加 CompletionReview 提示，采样 N 次。对 pos-bcb35740 的最终回合做"假设触发"版本作为正确例对照。统计三类回答：引用 login shell 回执放行；标记 PATH 未解决；提出新测量（例如在非 login shell 中 `which sqlite3`）。正确例上统计错误阻塞与是否破坏已正确状态。

不值得继续的判定：失败例中多数样本直接引用 login shell 回执放行；或正确例上出现阻塞并引发破坏性动作。

### L2 固定候选关闭审核对照（需模型调用授权）

基线 Sentinel 对 加 closure_review 的 Sentinel，在 D1 到 D7 与 pos-41c50c step 12 的"清空全部缺口"候选上对照。统计错误拒绝、错误放行、unusable。pos-41c50c 该步当时没有目标相关开放记录，预期 closure_review 不改变判断，作为阴性对照。

### L3 有界真实运行（需单独授权）

同任务同预算，基线 shared_view（A 加 B）对 加 RJC。指标：官方 reward、错误放行、错误阻塞、复核后是否出现新工具动作、额外回合与 token、延迟。至少包含一个已知正确例任务。回放中"能触发"不计为修复证据。

关键消融：拿掉 I3 只留账本与面板；拿掉 I2 配对只留开放列表。若两者去掉效果不降，RJC 只是更复杂的记账。

## 9. 与历史工作的差异

| 历史 | 当时结果 | RJC 的差异 |
|---|---|---|
| DCEC-v0 决策条件化证据转换控制 | Fyne R2 2/7，Supervisor 线路 | 不要求模型声明 scope；只用回执与缺口两种结构化对象；接在 PoS/PMA 线路 |
| CRS contrast 加两回合确认 | Fyne 1/7 | 不要 alternative/discrimination 自由文本；枚举对象是 PoS 缺口与账本配对；机械校验引用 |
| M2-D 直接依赖失效通道 | 101 边界 0 触发，回退 | 不依赖模型声明依赖；失败记录由回执机械产生，三次运行各 4 到 5 条 |
| M4 口头 uptake 判定 | 8ff2675f 负结果 | 复核后 Task 要么引用回执要么执行动作，二者都可机械记录 |
| 提交 A/B 审核语义与引用绑定 | 离线通过，未真实验证 | 互补：A/B 修审核判断，RJC 补关闭证成与完成边界 |

## 10. 风险与不覆盖

- pos-41c50c 型链条：从未产生失败回执，验证方式本身不具区分力。I1 到 I3 都不覆盖，只有 I2 的"脚本并列"在有配对时可能有用。写入适用边界。
- 命令词解析是启发式，`configure`、`grep` 等常见词会产生无关记录；目标相关性过滤是必要的，也会漏掉命令词与任务词面无关的失败。
- 复核回合可能被 Task 一句话带过。这是 L1 要回答的问题，不预设结果。
- PMA 冻结与 I5 的关系：I5 只改 shared_view 对 selection 的渲染，不改 PMA 代码、提示、触发或写入，与"只修 PoS"的决定兼容，但需主线程确认。

## 11. 阶段计划

大型目标：验证"回执证成的缺口关闭"是否减少错误放行而不增加错误阻塞。

阶段 1：账本、面板、审核输入、记忆标签（I1、I2、I4、I5）。文件：rjc_v0_20261021/failure_ledger.py、shared_view.py（扩展）、test_rjc_ledger.py。验证：以三次归档为夹具的单元测试，断言 §1.3 表中的记录数、关闭配对与目标相关性；既有 test_shared_view 在复制目录下全部通过。预计 diff 400 行以内。停止点：报告测试输出。

阶段 2：完成复核（I3）。文件：GA agent_loop.py 约 15 行（新 worktree），worker.py 一个命令分支与白名单，single_run.py 与 live_launcher.py 白名单，test_rjc_completion_review.py。验证：假 provider 下 no_tool 两次提议，第一次 CONTINUE 且 next_prompt 含三条缺口，第二次 ALLOW；gate 异常走 FAIL_OPEN；正确例夹具不触发。预计 diff 300 行以内。停止点：报告。

阶段 3：L1 固定上下文重放。需要模型调用授权、样本数与预算。停止点：按 §8 判定是否继续。

阶段 4：L2、L3。各需单独授权。

## 12. 需要用户决策

1. 是否同意在新路径建新 worktree 与分支进行实现，停着的 worktree 不动。
2. 候选名 pos_pma_rjc_v0 与三处白名单的改动边界。
3. 阶段 2 对 GA agent_loop.py 的约 15 行改动是否接受，或要求完全复制 GA。
4. I5 的记忆标签是否视为与 PMA 冻结兼容。
5. 阶段 3 的模型调用授权在阶段 1、2 完成后另行申请。
