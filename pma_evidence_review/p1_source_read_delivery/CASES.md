# 冻结的六例维护材料

这些是开发材料，不是留出集；真实调用前已固定任务、初始 bank、八轮窗口、事件 ID、旧来源目录和观察维度。维度只供父线程审计，模型看不到；不规定唯一措辞，也不强迫调用读源。正常保存新 ID、删除旧 ID 不视为内容失败。

| 文件 | 来源 | 观察范围 |
| --- | --- | --- |
| 01-local-success-scope.json | 公开 lean SQLite，维护步14 | 全路径运行的局部结果与 PATH 声明的范围 |
| 02-checkpoint-not-new-install.json | 公开 no-review SQLite，维护步9 | 重读背景与 checkpoint 不应变成又一次安装执行 |
| 03-no-new-result-history.json | 公开 no-review SQLite，维护步17 | 重述已有结果时不扩写完整经历流水账 |
| 04-counterevidence-to-old-claim.json | 公开 lean OCaml，维护步28 | 新可见重建结果与旧“正确修复”自述的区别，不新增根因诊断 |
| 05-distinct-executions-same-output.json | 人工对照 | 不同事件/参数产生同输出仍是不同执行 |
| 06-optional-read-preserve-correct-memory.json | 人工对照 | 不同 workspace 的值不应覆盖正确旧范围；读源按需 |

四个公开案例只取指定步及之前的可见成员。初始 bank 是当时 memory_derived 可见文本的格式重建，来源关联由匹配的既有写入与历史请求重建；合成 metadata、匿名 task ID 和呈现设置均明确标注，不冒称原生产 manifest。没有读原生评价或加入后续答案。
完整来源、成员/ZIP SHA、事件 ID 和每例 SHA 见各 JSON 与 INDEX.json。GA20 包仅下载并列过成员，未取其任务正文；没有读取正在运行的 RStan／电路任务。
