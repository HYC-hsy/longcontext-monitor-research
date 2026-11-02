# DMS原文选择＋GAP短索引＋输入历史回查

已测、已发布源码 `bbc225f9b4793c6109ba42efee84d7720b673d83`，分支 pma-dms-gap-index-20261102。本文档最终交付SHA见主线程回复。独立入口dms-gap-index-v1，旧dms-inspired-v1、source-links-v1/source-read默认路由、P2均不改。本轮只P1工程，无真实模型/Task/P2/评价调用，效果由主线程另行审计。

GAP是任务相关、仍需满足的条件或仍需得到的答案；不是失败日志、猜测原因或行动计划。仅memory_keep(category=gap)要求pending短文本（非空、<=240字符），原样保存换行；knowledge/procedural仍禁止生成正文。索引标generated_unresolved_index_not_fact，来源原文独立保留。关闭应针对本项条件满足、问题得到回答或需要明确不再适用。失败回执可以回答发生了什么，但不满足尚待成功的条件；另一阻塞解除不能关闭无关项。这些语义是提示要求，不是工程判定。

每个生成窗口自动冻结真实已显示记录对应的底层bank内容/来源；DMS底层内容是材料ID索引，完整实际显示视图在model_input，不冒称模型看过所有原文。组读源先给目录，已删除旧记录可经合法H读取；H也可用于source_ids，不可delete。显式引用与生成前input coverage分别记录，未read就引用不等于读过/证实。cited_history_handles、原文关联和bank同次原子提交；按M引用继承已有明确H列表，不声称自动语义闭包。

复用A固定helper26ff924d，保留B冻结pending、动态原文字段、目录优先及完整页预算。坏coverage不遮蔽独立sources，也不签发坏H；合法explicit H目录可独立保留。短来源可两读后在第三轮keep，但长来源仍partial，四读/三逻辑轮不保证任意深度读完。

最终本地/固定远端各100/100离线通过，无依赖替身。SYSTEM/schema完整文件、差异、65项源码身份、原六例实际组装哈希、原始报告公开投影及逐文件MANIFEST均在本目录。原六例与初始bank未改。原目录dms_gap_index_delivery_20261102与其87/98项材料仅历史，不是本次最终身份。

HANDOFF先离线；真实Windows六例模板须主线程审查后明确放行，不能从本README推导启动许可。组合含展示修复、GAP和历史接线，后续结果不能分别归因；不宣称语义改善。
