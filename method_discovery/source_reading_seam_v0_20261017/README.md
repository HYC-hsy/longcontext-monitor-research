# Source-reading seam v0 · 2026-10-17

## 在线阅读入口

- [中文研究进展与当前判断](RESEARCH_UPDATE_ZH.md)
- [原型说明、五组对照与边界](PROTOTYPE_README.md)
- [简要机械检查结果](summary.json)
- [32 份假轨迹逐份浏览](TRACE_INDEX.md)
- [完整独立复跑记录](root_verified_results.json)
- [研究设计快照](design_contract_snapshot.md)
- [此前 54 次输入视图诊断](input_view_audit_snapshot.md)
- [来源与复用说明](PROVENANCE.md)
- [本次发布文件清单与哈希](PUBLICATION_MANIFEST.json)
- [发布副本离线复核回执](PUBLICATION_VALIDATION.json)

## 当前完成了什么

本次仅发布有限的离线研究原型与记录：在原版 PMA Phase 1 前增加一次可失败的依据重读，重读结果只进入 Phase 1；Phase 2 继续使用真实提交后的银行。未接入生产底座，也未修改其他目录。

独立复跑的 257 项机械断言通过；六份历史窗口、43 条记录的输入投影复现。32 份保留的假轨迹共 85 次脚本调用，真实模型调用为 **0**。没有 Task 续跑或效果评估；脚本安排的修订不能当成模型纠错能力或任务效果提升。

## 包装与复现边界

这不是独立可安装包。运行器仍依赖原有固定共享路径中的已审计 PMA 源码、测试入口与公共历史归档；复制此目录到另一台机器不保证可运行。依赖与哈希见原型说明和来源清单。此次未下载依赖、执行历史 Task 命令或调用模型。

为避免重复保存两份约 6 MB 的完整报告，本目录仅保留独立复跑的 `root_verified_results.json` 与对应空 stderr。原型说明中提到的 `results.json` 是原始运行输出名称；它不在本发布包中，也不与独立复跑文件声称逐字节相同。原始输出的哈希记录在发布清单中。

独立复跑完整记录 SHA-256：

`1a0708c87d1b7a17aa2dad592e47852216c62230600641e97a96ac06e71dd50b`

逐份 trace JSON 是为网页阅读生成的新序列化，逐项等于完整记录的对应数组值，索引见 `TRACE_INDEX.md`；不能称作 provider raw。

`PROTOTYPE_README.md` 是原始 README 的逐字节副本。`PROVENANCE.md` 与设计快照仅做发布用措辞整理，改动类别和原文件哈希均在发布清单中；研究判断与范围没有改变。原始共享文件未被改写。`manifest.json`、`reuse_manifest.json` 的发布副本已同步更新涉及的文件名和哈希；原始副本哈希与变更类别保留在本次发布清单中。完整独立复跑记录对应原始源码与文档快照，不能误称为发布副本的原始执行记录。发布副本另经同一隔离离线入口复核，257 项机械断言通过、stderr 为空，仍为零真实模型调用；仅保留该次复核的紧凑回执，避免第三份重复大报告。

## 源码

- [adapter.py](adapter.py)：Phase-1 接缝、来源包与实际银行回执
- [checks.py](checks.py)：合成情形、脚本回答和断言
- [run_fake.py](run_fake.py)：受限离线运行入口
- [input_views.py](input_views.py)：复用的确定性输入投影
- [reference_adapter.py](reference_adapter.py)、[reference_evidence.py](reference_evidence.py)：既有测试适配与证据读取
- [PMA_LICENSE](PMA_LICENSE)：保留的原版 Apache-2.0 许可

本归档不会自动推进下一阶段；真实成对推理、Task 行动对照与独立语义评价仍需另行确定范围并授权。
