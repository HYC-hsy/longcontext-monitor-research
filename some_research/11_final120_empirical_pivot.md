# Final120 全量普查带来的实证转向

更新时间：2026-08-16  
性质：当前实证依据与研究转向记录  
权威逐题数据：`exploration/full_survey/final120_full_semantic_survey.jsonl`

## 1. 为什么进行这次普查

此前方法探索主要由少量代表案例、PMA 等近邻论文和经典理论驱动。少量案例能够证明现象存在，却不能回答哪些问题在 GenericAgent 的真实历史运行中更频繁，也不足以决定第一篇论文应优先解决什么。

因此，本轮对 Final120 的每道任务建立统一记录，对齐冻结 task、M14 选中 run、manifest、trace、可用语义日志/最终产物和 verifier。审计不把长轨迹、低 reward、文件存在或进程完成自动归因成遗忘。

## 2. 已落盘产物

- 人类可读总报告：`exploration/full_survey/FINAL120_FULL_SURVEY_REPORT.md`
- 120题完整主表：`exploration/full_survey/final120_full_semantic_survey.jsonl`
- 可筛选CSV：`exploration/full_survey/final120_findings_table.csv`
- 可浏览Markdown表：`exploration/full_survey/final120_findings_table.md`
- 完整性审计：`exploration/full_survey/final120_full_semantic_survey_audit.json`
- 可重复构建脚本：`exploration/full_survey/build_final120_master.ps1`

完整性结果：120行、120个唯一ID，与冻结Final120相比 missing=0、extra=0、duplicate=0、必需字段缺失=0。

## 3. 全量主标签

| 主标签 | 数量 | 对120比例 | 解释 |
|---|---:|---:|---|
| insufficient_evidence | 62 | 51.7% | 历史产物不足以判断认知原因，不代表成功或失败 |
| premature_completion | 28 | 23.3% | 用弱代理证据支持完成声明，集中于RoadmapBench |
| planning_capability | 12 | 10.0% | 当前证据更支持实现、数学或调度能力不足 |
| success_no_drift | 9 | 7.5% | 终局成功或受控状态完整的正对照 |
| confirmed_representation_omission | 8 | 6.7% | 7个MemGym notes遗漏和1个自然提交义务遗漏 |
| confirmed_commitment_violation | 1 | 0.8% | 最终产物直接违反明确交付契约 |

这些不是总体发生率：来源异质、选题机制不同，而且一半以上证据不足。可信结论应使用来源内分母。

## 4. 三项决定研究方向的发现

### 4.1 受控表示遗漏：MemGym-DR 7/10

每题有三个future-required facts，在三轮full eviction和200-token notes条件下：

- 7/10至少遗漏一个必需事实；
- 30个必需事实保留20个，micro recall=0.667；
- 最严重任务保留0/3；
- 3/10完整保留，可作正对照。

这支持“任务状态表示会遗漏未来行为需要的信息”。但judge关闭，尚需paired repair证明补回事实能改变最终答案。

### 4.2 完成证据偏移：RoadmapBench 28/31

反复出现的行为链是：

```text
读取并在checkpoint保留N个目标
→ 完成部分实现
→ import、compile或自写smoke test通过
→ 宣称全部完成
→ native verifier只通过0..5个phase
```

这不能简单解释成“忘记目标”：目标往往仍在checkpoint。偏移发生在完成语义和证据标准上——Agent把弱代理提升成了完成证明。

代表任务：

- `pyg-2.3.0-roadmap`：声称12项均验证，native仅2/12；
- `spc-3.4.0-roadmap`：声称6/6，native为5/6；
- `fbr-2.43.0-roadmap`：声称7项完成，native为5/7；
- `glz-7.0.0`、`vbt-1.1.0`：声称已创建的交付路径实际不存在。

因此提出阶段性现象名：**completion-evidence drift**，即长程Agent的完成判断逐渐由真实验收条件漂移到较弱代理。

### 4.3 自然表示遗漏：ClawBench T071

原指令给出提交URL；Agent约50轮后完成研究，最终checkpoint保存10篇论文并写`Ready to submit`，但未保存URL和提交终止义务。下一轮Agent明确表示看不到/不记得URL，向用户询问后结束，且提交interception缺失。

这是目前最完整的自然证据链：

```text
早期获得义务
→ 长程执行
→ 外部任务状态没有保存义务
→ 后续使用失败
→ 任务过早结束
```

它证明外部表示遗漏和行为后果，不证明模型内部actual context在某一轮发生了遗忘。

## 5. 对旧候选的裁决

| 候选 | 新状态 | 原因 |
|---|---|---|
| P1 行为充分状态编译 | 升级为核心表示层 | 有MemGym频率证据和T071自然案例 |
| P3 commitment shield | 改造并升级为completion kernel | Roadmap大规模显示完成证据/终止义务问题 |
| P2 保守干预选择 | 保留为动作选择层 | 历史单轨迹没有因果价值证据，需新分叉 |
| P4 主动再观察 | 降为动态环境扩展 | 全量普查没有confirmed staleness primary |

旧的“动态状态＋主动提醒”不再是核心创新；提醒只是一种恢复动作。

## 6. 新的实证主线

> 长程Agent的外部任务状态既可能遗漏未来义务，也可能保存目标却缺少支持完成声明的充分证据。第一篇论文应研究如何编译、维护和验证一个面向未来行为、携带验收证据的可修订任务状态，并在证据不足时阻止错误闭合。

这条主线同时解释受控记忆遗漏、自然终止义务遗漏和真实工程任务的弱代理闭合。

## 7. 使用纪律

- 不把28/31外推为所有Agent的过早完成率；
- 不把62个证据不足任务算作无偏移；
- 不把`note_fact_recall`当成最终任务reward；
- 不把目标仍在checkpoint却实现失败归因成activation failure；
- 不声称已证明completion gate会提升结果；提升必须由paired checkpoint实验给出。

