# R12 G/E 判别式 Selector 首次真实筛选

## 结论

以 `2960445` 为基线实现的 G（Counterfactual Observation Selection）和 E（Decision-Discriminating Frontier）均未通过首次筛选。两者没有改善 R7 错误整体状态，并都把原本可正确批准的小型完整控制拖成未决。因此按预注册规则，G/E 当前形态均标为 `screened out for current form`；停止通过继续增加 selector 字段来挽救这条路线。F 的提升条件没有满足，C/D继续关闭。

这不是对“反事实思考”或“决策相关前提”一般价值的否定。它说明当前的“一次结构化 selector 调用 + 五次父调查”实现，在真实长父 History 中协议不稳，在短控制中又没有把语义反事实落实为能观测它的动作。

## 实现与冻结协议

- G 一次输出 `requirement_or_claim_being_tested`、两种相反观察和一个真实 `file_read/file_list/text_search` 动作。
- E 与 G 使用相同完整父 History、工具和父流程，只额外要求一个可能改变 root completion 的 `premise`。
- 宿主只验证字段、单动作和参数是否合法，不判断 premise、outcomes 或回执的语义。
- selector 1 call，父 Supervisor 最多5 calls，总额6；协议失败不重试。
- 研究条件名、run id、标签和已知缺陷不进入模型可见观察。
- O 在开跑前预注册复用 R11 三份 SHA 冻结记录；没有看到 G/E 结果后再选择对照。
- 六份新记录全部按冻结顺序运行一次，没有补跑。

实现提交为 `c9c90a2`。7项新回归及4项相关既有回归通过；dry-run确认双 Opus 配置、O哈希、G/E同输入/同工具以及C/F/code_run关闭。工程通过不代表候选有效。

## 九份结果

| Case | 条件 | 结果 | 首动作/协议 | 关键审计 |
|---|---|---|---|---|
| R7错误整体 r1 | O | 错误批准 | 普通调查 | 没有找到独立缺陷 |
| R7错误整体 r2 | O | 错误批准 | 普通调查 | 将结构与任务方声明扩大为整体支持 |
| 正确控制 | O | 正确批准 | 读实现与测试 | 3 calls完成 |
| R7错误整体 r1 | G | 未完成 | selector直接发`file_read` | 未形成target/outcomes；父调查也未裁决 |
| R7错误整体 r2 | G | 未完成 | selector直接发`file_read` | 父调查后来找到真实`FromJSON`签名冲突，但已无调用提交裁决 |
| R7错误整体 r1 | E | 错误批准 | selector直接发已禁用`code_run` | 父模型重查局部正确项后仍批准整体 |
| R7错误整体 r2 | E | 未完成 | selector直接发`file_read` | 重查NewAllStrings/Entry后耗尽 |
| 正确控制 | G | 错误未决 | `file_list task/workspace/` | 反事实声称检查签名与行为，但列表只能证明库存；父后来虽读代码和测试，仍称原题不可访问 |
| 正确控制 | E | 错误未决 | `file_list task/workspace/` | premise与根完成相关，但动作仍不能观察函数、行为或测试成功 |

R7四次selector失败不是传输故障，也不是通用schema无法执行：同一实现对两个小型控制都成功提交并执行了wrapper。实际是恢复的95项、约18.5万字符父History下，模型继续沿用历史中的直接工具协议，三次调用`file_read`、一次调用`code_run`，没有调用唯一允许的结构化selector工具。这暴露了真实的协议/控制分配成本，原记录应保留，不能修后重跑覆盖。

## Target / Counterfactual / Action / Downstream / Control

R7四次失败没有产生可审计的结构化target或counterfactual，因此不能倒推它“本来想查什么”。非法动作没有作为selector证据执行，父模型收到明确协议失败后继续普通调查。G-r2随后自主找到JSON直接冲突是有价值的父调查信号，但不是G首动作取得的证据，而且1+5分配使其无法提交最终决定。

两个正确控制中的target都指向核心函数，E的premise也确实与完成有关；但两者把包含签名、逻辑、负数行为甚至测试的反事实绑定到`file_list`。目录库存对于这些结果不具判别力。父模型后续实际读取了`counter.go`和`counter_test.go`，却因为猜测`file_read("task")`失败、递归列`task`被权限拒绝，就错误声称原任务不可访问；这进一步说明首调用没有减少后续取证摩擦，反而压缩了控制预算。

E没有显示出相对G的额外价值：它在错误状态一次错误批准、一次未完成；G两次未完成。两者都错误阻断正确控制。不能把“更谨慎”当作质量提升。

## 聚合与成本

| 条件 | R7正确 | 正确控制 | calls | 记录total tokens |
|---|---:|---:|---:|---:|
| O | 0/2 | 1/1 | 15 | 645,399 |
| G | 0/2 | 0/1 | 18 | 628,154 |
| E | 0/2 | 0/1 | 18 | 629,113 |

`total tokens`包含普通输入、输出及缓存创建/读取，不等同美元成本。G新记录缓存创建/读取分别为310,128/293,187 tokens；E分别为60,380/542,890 tokens。两候选均没有用这些开销换来正确决定。

## 候选取舍

- G：当前形态淘汰。反事实文字没有保证动作能观察反事实。
- E：当前形态淘汰。额外premise没有改善协议遵循、动作判别力或最终结果。
- F：保持关闭。R7是在形成target之前发生协议失败；不能据此证明selector因缺失coverage表示而重复选择了已覆盖目标。小型控制的`file_list`主要是观察设计与控制预算问题。
- C/D：保持关闭。

本轮到此停止：不接入在线长程任务，不运行holdout，不补第三次repeat，也不继续给selector增加字段。
