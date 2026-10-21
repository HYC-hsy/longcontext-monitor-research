# RJC-v0 阶段 1 报告：账本、面板、审核输入、记忆标签

日期：2026-10-21。分支 rjc-v0-20261021，基于 crs-v0-20261007 的 7e23acc87c89b5972b3106f3457b707971839ebd。
worktree：E:/longcontext-rjc-v0-20261021。停着的 crs-v0-20261007 worktree 未改动。

## 阶段目标

实现 DESIGN_RJC_V0.md 中的不变量 I1、I2、I4、I5，并产出 I3 的复核载荷（不接 GA）。零模型调用、零 Task 运行、零官方评价。

## 完成内容

- `failure_ledger.py`：回执账本。code_run 回执 exit 非零或含失败行时开记录，记录失败命令词与失败行；只有更晚、exit 0、无失败行且在命令位置调用同一命令词的 code_run 回执能关闭；`bash -c '...'` 内层命令与 `which`/`command -v` 的探测目标计入命令词。每条关闭保存失败调用行、关闭调用行、关闭回执 stdout 头部。目标相关性由任务原文词与命令词的包含关系给出。面板段、关闭审核、完成复核三种投影各有字符上限，超出部分计数。
- `rjc_view.py`：在 pos_pma_shared_view_v1 的类上以导入加子类方式扩展，不复制、不修改 complement 目录与两个 vendor。RJCSentinel 在 consistency lane 追加一条 system 消息，内容是本次审核被移除的缺口与账本中目标相关的开放记录和配对；RJCBeliefManager 只替换 sentinel 类并保留 shared_view 的全部开关；RJCEpisode 在 PoS 更新前记账，在 PMA 写入后、冻结选择前给新条目打写入时账本标签，面板追加账本段，并提供 completion_review 载荷。
- `test_rjc_v0.py`：9 项测试。三次 SQLite 归档作为只读夹具；假角色下的 episode 接线测试覆盖面板、审核输入、记忆标签、复核触发与不触发、角色调用次数不变。
- `offline_replay/`：生产账本对三次归档的重放报告 `ledger_report_v0.json`，以及 pos-68764e 终态下 Task 会看到的面板段与复核清单渲染 `RENDERED_68764E_PANEL_AND_REVIEW.txt`。

## 文件改动

全部为新增，位于 method_discovery/rjc_v0_20261021/：

| 文件 | 行数 | 说明 |
|---|---|---|
| failure_ledger.py | 约 300 | 账本与三种投影 |
| rjc_view.py | 约 190 | shared_view 扩展层 |
| test_rjc_v0.py | 约 340 | 离线测试 |
| offline_replay/replay_with_ledger.py | 约 70 | 归档重放 |
| offline_replay/render_68764e_panel.py | 约 25 | 面板渲染 |
| offline_replay/replay_invariants.py | 约 250 | 设计期探索脚本，保留作记录 |
| DESIGN_RJC_V0.md、STAGE1_REPORT.md、STAGE1_TEST_OUTPUT.txt、offline_replay/*.json、*.txt | 文档与产物 | |

对 pos_pma_complement_v1_20261019、pos_upstream_ga_v1_20261017、curator_supervisor_convergence_v0、GenericAgent-main 的 diff 为空。

## 验证

- 命令与原始输出见 STAGE1_TEST_OUTPUT.txt。解释器为开发线程使用的 bench_runtime/m4/harbor-env 的 Python 3.13.14。
- `test_rjc_v0`：Ran 9 tests，OK，exit 0。
- 回归 `test_shared_view`、`test_candidate_core`、`test_memory_adapter`：Ran 45 tests，OK，exit 0。这些文件未改动，回归只证明新目录没有破坏导入环境。
- 归档重放（ledger_report_v0.json）：

| 运行 | 记录 | 目标相关 | 结束时开放且目标相关 | 面板段字符 |
|---|---|---|---|---|
| pos-68764e | 5 | F4、F5（sqlite3 两次 command not found） | 0 | 1708 |
| pos-41c50c | 5 | F3、F4（gcc/gcov/make 安装期失败，均被后续回执关闭） | 0 | 1846 |
| pos-bcb35740 | 4 | 无 | 0 | 0 |

pos-68764e 的 F4、F5 由第 15 回合回执关闭，关闭调用行为 `bash -l -c 'which sqlite3 && sqlite3 --version'` 与 `/app/sqlite/bin/sqlite3 --version`，失败调用行为 `which sqlite3`、`sqlite3 --version`。面板段把两组调用行并列显示。

## 完成条件核对

- [x] I1：模型文本、PoS 缺口移除、PMA 记忆写入都不能关闭记录；同回合或更早的成功、非 code_run 回执不能关闭（test_model_text_cannot_close_and_only_later_receipt_can）。
- [x] I2：每条关闭保存配对，面板与复核清单显示失败调用行与关闭调用行（test_sqlite_failure_pairs_match_archive_facts、test_panel_shows_failure_then_pairing_and_tags_memory）。
- [x] I4：候选移除缺口时 consistency 请求多一条 closure review 消息，命名被移除缺口；无移除且无开放相关失败时不追加（test_closure_review_attached_only_when_gap_removed_or_failure_open）。
- [x] I5：失败开放期间 PMA 写入的条目带写入时标签，标签随冻结选择进入 belief 候选输入与 Sentinel 的 shared_selection，且不随后续关闭改变；无关失败不打标签（两项 episode 测试）。
- [x] I3 载荷：开放缺口或目标相关开放失败存在时 fires 为真并生成清单；正确例不触发。GA 接线属于阶段 2，未做。
- [x] 角色调用次数不变：测试断言 belief 3、consistency 3、PMA 6 与无 RJC 时一致。
- [x] 面板与复核字符上限生效（test_panel_budget_omits_tail_items_with_count）。

## 限制和异常

- 命令词与失败行解析是启发式。`file` 工具缺失在三次运行中都开放到最后，被目标相关性过滤掉；命令词与任务词面无关的真实失败会被漏掉，这是设计中承认的边界。
- 目标相关性会把 pos-41c50c 的 gcc/gcov 安装期失败判为相关并显示其关闭配对。这些配对是正确的历史事实，但对该运行的最终失败无帮助。
- 复核回合是否改变 Task 行为完全未验证，需要阶段 3 的模型调用。
- 开发线程在我开始后推进了 4 个提交（3c4901c5 到 7e23acc8）。本分支基于最新的 7e23acc8，shared_view 的 unknown_fallback 身份与精确引文匹配等补修都已包含。
- method_discovery/rjc_v0_20261021 被某条 .gitignore 规则忽略，提交时需处理（见提交说明）。

## 人工审阅建议

阅读 offline_replay/RENDERED_68764E_PANEL_AND_REVIEW.txt。判断标准只有一个：一个人看到"失败时 `sqlite3 --version` 裸调用，成功时 `bash -l -c` 与绝对路径"并列，是否能意识到两者的执行上下文不同。如果连人看了也不觉得有区分力，阶段 2 不必做。

## 下一阶段建议（不自动开始）

阶段 2：完成复核接入 GA。GA agent_loop 在 complement 分支受 GA_POS_COMPLETION_REVIEW=1 保护设置 completion_gate，约 15 行；worker 新增 completion_review 命令分支；候选名 pos_pma_rjc_v0 加入 worker、single_run、live_launcher 白名单；假 provider 测试两次提议先 CONTINUE 后 ALLOW。预计 300 行以内。
