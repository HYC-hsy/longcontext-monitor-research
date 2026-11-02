# context 候选：读取与删除使用同一冻结标识

本次只修工程接口，源码提交 `449817cd94b846fef9dee995c6784463f5af39a3`。候选仍为 `source-links-context-v1`；不接入 DMS，不改变整理判断准则，不增加模型步骤。

`memory_read_source` 与 `memory_delete` 共用宿主解析器：已展示的 M 别名和原 memory_id 指向同一冻结对象。删除仍兼容维护开始时已存在的明确原 ID。M 别名与真实 ID 如指向不同对象，读和删都返回 `ambiguous_memory_id`，不优先猜一种解释。E、TASK、STATUS 可读，不因此可删；来源事件别名不会被转换成记忆删除目标。

维护开始时冻结 ID、内容哈希、类别及来源绑定。之后条目消失返回 `entry_not_found`，内容/类别/绑定变化返回 `memory_target_changed`，未知标识返回 `source_not_displayed`。新保存的对象不冒充原别名目标。两种读取继续共用四次预算，部分/未关联/缺历史回执仍是可消费的数据，不自动成为语义失败。

原始模型 tool_calls 和参数保留；执行前只复制调用并解析 ID。读回执原有 `target` 记录实际目标，删除回执另记 `target_resolution.resolved_memory_id`，操作记录仍为真实 ID。不给分页读回执追加未计入 8000 字符预算的元数据。

未知/无效工具、无效标识或删除失败后，context 候选停止同批后续操作，回执为 `not_executed_after_tool_failure`。此前成功提交的操作保留；这不是整批回滚。旧 `source-read`、`source-links-v1` 的 system/schema/行为不启用新解析器或失败策略。共享基类只增加默认关闭的失败钩子和原值不变的显示标题属性。

工具说明和输入标题只说明 M 别名/ID 的一致接口；system 判断准则不改。Windows 测试修复 `1ac74ae6274b4fcf9f10dec452c59bfba2a6e481` 已核对并采用同样的 UTF-8 字节写入；另一处同形测试写入也改为显式字节。生产哈希校验未放宽。Windows 离线复验须设 `PYTHONUTF8=1`，详见 HANDOFF.md。

实际提示差异只有三处，供完整性、简洁性、自然性复检：

1. 输入标题由 `Stored summaries (derived; IDs for deletion, aliases for sources)` 改为 `Stored summaries (derived; memory IDs or M aliases for reading/deletion)`。
2. delete 工具说明追加 `Accepts a frozen displayed M alias or an original memory ID; never E/TASK/STATUS.`
3. read 工具说明追加 `Frozen M aliases and displayed memory IDs resolve identically; ambiguity is rejected.`；原有 context 说明不变。

`SYSTEM.txt` 逐字未变，SHA-256 仍为 `a070c58dc8d79bdd6b433907406d85a20e479537cfa7be086d713b511dbd3469`。没有增加案例专用规则、整理标准或证据审判要求。

## 验收

`--source-links-context`：78 tests，0 failures/errors/skips，15.258 秒。旧 58 项及此前 context 回归继续通过；新增真实形状、歧义/真实 ID/已删/内容与绑定变化、失败后停止、重复删除保留先前提交、缺历史可继续等检查。公开原始报告投影为 `delete-interface-checks.*`，仅替换机器路径；原件 `/tmp/context-delete-release.*` 保留。

最直接的工程验收来自公开失败归档 `992f7b56f95afffb9d09197d12baa355ee79916c`：小夹具 `pma_evidence_review/fixtures/context_delete_a04_replay.json` 逐项保留实际三轮可见 tool_calls 的名称和参数。假客户端依次回放 M2 sources → M2 context → delete M2 和其后五项操作：两次读取和删除均指向 `RL3HYG6d`，原条目确实删除，六项操作均提交，参数未改写。**这里只验证接口，不评价这些生成正文是否正确。**

归档中的 case04 与本仓冻结 case04 仅公开删减后的 source_manifest 元数据不同；夹具只替换该非模型输入字段，并验证重建对象与归档完整解析对象的规范 JSON 哈希相等。六例实际输入字段均与归档相同，既有本地冻结文件未改，见 `FROZEN_INPUT_CHECK.json`。没有复制 345 KB case04 或整运行目录。

没有加载真实 profile，没有真实模型、Task、P2 或 eval，没有补跑 A05–06/B，没有重跑旧真实组。原始失败归档未覆盖。真实模型是否会选择合适的记忆修改仍未验证。

## 文件与交付

- `p1_context_agent.py`：共享冻结解析与候选专用失败分类。
- `p1_linked_agent.py`：默认关闭的批次失败钩子、原值不变的显示标题属性。
- `test_p1_context_agent.py` 和 4.9 KB 回放夹具：定点及真实可见调用回放。
- 本目录：更新运行身份、schema、最小输入说明差异、测试与冻结输入证据、manifest 和 Windows 指令；历史报告保留。

所有 62 项运行源码须按当前交付重建身份；旧源码清单和旧 CLI 报告是历史证据，不能直接替代本次身份。最终固定 SHA 与远端回读结果由交付回复给出。
