# M3 Control-Theory Reading Index（2026-08-28）

本索引记录 M3 调查实际使用的经典资料、公开入口、本地状态和适用边界。资料被引用为机制灵感，
不表示 LongContext 方法取得了原理论的数学保证。

| 主题 | 资料 | 公开入口 | 本地状态 | M3 用途 |
|---|---|---|---|---|
| Event-triggered control | Åström & Bernhardsson (1999), *Comparison of Periodic and Event Based Sampling* | https://lup.lub.lu.se/record/8516737 | `papers/1999 Astrom Bernhardsson - Comparison of Periodic and Event Based Sampling.pdf` | 以高信息事件触发深审，而非固定频率 |
| Supervisory control | Wonham, Cai & Rudie (2018), *Supervisory Control of DES: A Brief History* | https://www.control.toronto.edu/people/profs/wonham/Wonham_ARC_SCDES-brief-history.pdf | `papers/2018 Wonham et al - Supervisory Control of Discrete Event Systems Brief History.pdf` | maximally permissive/minimally restrictive 监督 |
| Rational metareasoning | Russell & Wefald (1991), *Principles of Metareasoning* | https://iiif.library.cmu.edu/file/Newell_box00014_fld01011_doc0001/Newell_box00014_fld01011_doc0001.pdf | `papers/1991 Russell Wefald - Principles of Metareasoning.pdf` | 信息/计算价值来自改变下一外部行动 |
| Partial observability | Cassandra, Kaelbling & Littman (1994), *Acting Optimally in Partially Observable Stochastic Domains* | https://cdn.aaai.org/AAAI/1994/AAAI94-157.pdf | `papers/1994 Cassandra Kaelbling Littman - Acting Optimally in Partially Observable Stochastic Domains.pdf` | epistemic state 与 information action |
| Human supervisory control | Sheridan, *Automation / Human Supervisory Control* | https://www.hfes.org/Portals/0/Documents/Sheridan.pdf | `papers/2002 Sheridan - Humans and Automation Supervisory Control.pdf` | 规划、监视、诊断、干预、学习的职责循环 |
| Model predictive control | Rawlings, Mayne & Diehl, *Model Predictive Control* | https://sites.chemengr.ucsb.edu/~jbraw/mpc/ | 公开作者页面；本轮未复制整本 | 有限时域、只执行下一步、重观察 |
| Sequential experiment | Chernoff (1959), *Sequential Design of Experiments* | https://statistics.stanford.edu/technical-reports/sequential-design-experiments | 公开 Stanford 记录 | 自适应选择下一观察与停止 |
| Three-valued RV | Bauer, Leucker & Schallhart (2011), *Runtime Verification for LTL and TLTL* | https://doi.org/10.1145/2000799.2000800 | 公开论文记录 | true/false/inconclusive，保留 UNKNOWN |
| Assurance case | Kelly & Weaver (2004), *The Goal Structuring Notation--A Safety Argument Notation* | https://www.researchgate.net/publication/228990118_The_goal_structuring_notation-a_safety_argument_notation | 公开作者稿入口 | claim--argument--evidence 与 defeater/revision |

## 完整性检查

本轮下载的五份本地 PDF 均检查为 `%PDF-` 文件头并可由 `pypdf` 解析：

- 1999 Åström--Bernhardsson：7 页；
- 2018 Wonham--Cai--Rudie：7 页；
- 1991 Russell--Wefald：1 页公开稿；
- 1994 Cassandra--Kaelbling--Littman：6 页；
- 2002 Sheridan：2 页公开稿。

曾有一次 AIJ PDF 下载产生 0 字节占位并锁定文件；该失败占位和卡住的下载进程均已清理，
没有把不完整文件保留在研究库。

## 使用警告

- 不从 Åström 的一阶随机系统推导 Agent 性能或稳定性结论。
- 不声称自然语言任务构成完备的 Ramadge--Wonham legal language。
- 不为缺少概率模型的语义状态伪造 POMDP belief probability 或 SPRT likelihood。
- 不把 MPC 的数值稳定性定理转移到 LLM repair loop。
- 不把 LTL 三值监控器当作在线 checker；只借鉴 partial trace 的 inconclusive 语义。
