# PMA-gap 两阶段提示限定调优（2026-10-22）

本次只修改 `gap_prompts.py` 的模型可见英文提示。第一阶段仍使用原 PMA 的维护系统提示和四个工具，另加 `memory_save_gap(content)`；第二阶段仍由原 PMA 的 `context_for_action` / `no_intervention` 协议决定提醒或静默。没有新增角色、工具、调用轮次、自动关闭或审核门禁。普通 PMA 的 vendor 文件未改。

## 行为差异

1. 第一阶段在测试创建、修改、执行或完成宣称后，更具体地检查可见测试的覆盖范围、断言强度、原始结果与总结是否矛盾；不把有缺陷的检查直接等同于实现失败。
2. 第一阶段按新证据维护已有 gap：已解决则按真实 ID 删除，部分解决则 delete+save 保留剩余范围，status 更新不自动关闭 gap；有价值的真实修复经历可由原 `memory_save_procedural` 保存。删除重复或误报不自动生成成功经历。
3. 第二阶段允许在证据已经可见但被 Task 错误使用时作具体提醒；正在恰当处理或旧 gap 已被充分证据解决时仍可静默。

Phase2 对钉扎 vendor 原文只作以下三处单次替换，随后追加新的 `ATTENTION` 段落；原 `PHASE2_SYSTEM` 常量不变：

| vendor 原文 | 本方法派生文本 |
| --- | --- |
| `- The information you'd provide is already visible in the recent trajectory` | `- The information is already visible in the recent trajectory and is being applied appropriately` |
| `- Don't include information already visible in the recent trajectory` | `- Avoid repeating visible information unless it identifies a concrete, task-relevant omission or misapplication of evidence` |
| `- You're not confident that a specific fact is being forgotten` | `- You cannot identify a concrete task-relevant omission or contradiction supported by the available evidence` |

新增提示全文见 `gap_prompts.py`；不以此文档代替实际发送的 system 文本。固定假响应只验证工具和调用接线，不验证真实模型的判断能力。

## 开发案例（既有运行 pma-d1847af4750941c0 的公开可见轨迹，非盲测）

| 锚点 | 可见证据与期望 | 不可接受的推断 |
| --- | --- | --- |
| C18 | 有限回执未证明 curl 可用；保留工具可用性的未知状态。 | 把可用性写成已验证事实再提醒 Task 使用。 |
| C29 | `head` 截取的目录列表仅覆盖局部范围；提醒须保留搜索范围。 | 断言 gcc 不存在。 |
| C43/C44 | 构建困难仍受原题预置 SQLite 源码约束。 | 将困难视为取消源码约束的依据。 |
| C52 | T51 已执行正确 gcov 命令并产生报告；对应旧文件名 gap 应按证据更新，必要时保存解决经历。 | 仅因旧 gap 残留要求重复验证，或顺手关闭 PATH gap。 |
| C54 | 原生 gcov 显示非零覆盖，自写统计显示零，且成功判定不足以支持所声称行为；应指出统计/判定缺陷。 | 将检查脚本问题直接说成 gcov 未工作。 |
| 静默对照 | Task 已根据充分证据恰当地处理问题。 | 因 gap 存在就强制提醒。 |

本轮不调用模型、Task 或官方评价；旧运行和 reward 未修改。新源码尚无真实模型效果证据，不能沿用旧源码认证。
