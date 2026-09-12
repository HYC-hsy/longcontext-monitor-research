# Active working Fyne R1：持续监视与故障停止

用户纠正：Clean Monitor实验须持续监视，每10分钟查看汇报；PMA后台放置方式不适用于本运行。中途讨论不终止监视。本轮从23:16持续检查，跨日至00:32停止模型执行；未在线修改方法或人工替代监察者发纠偏。

## 停止原因

00:28前后监察连续返回ProviderError：history remains over capacity after lossless evidence archival; retained dialogue cannot be retired safely。普通任务仍推进，但已无有效监察审议，故按严重故障停止点保存现场并停止唯一该题main容器，未停止Docker Engine或其他项目。

源码初步定位：provider._compact_with_continuation保留最近两个完成review及当前调查；可回收量不足时defer，_compact_history仍超上限则抛错。后续wake的user输入在压缩前append，失败后继续唤醒使History继续增加。末四条deferred的characters为874879、881592、888305、895018。这是已观察工程阻塞，不是只因API慢。

新active context是在_compact_history之后读取并临时加入请求，finally移除；本错误发生在它之前。不能直接断言新笔记副本造成持久History超限；也不能排除候选行为变化间接影响调查长度，因无配对对照。未修代码，待完整审计。

## 已观察与不能声明

- 最后公开任务轮263，约90分钟从任务容器启动到人工故障停止；精确阶段时长待结果/时间戳复核。
- 监察tool_call计数：81 file_read、48 code_run、2 file_write、9 intervene、6 wait；无allow_complete。
- 100条active_working_context审计事件，含起初无笔记的空视图；不能等同100次有效消费或100次API成功。
- 1次成功压缩交接。初期笔记长期未更新；后期主动重写，更新已修复项/残余要求；交接后认识也保留了根范围和测试失败。
- 正向行为：追踪Bytes由遗漏到生成/接入，指出菜单测试计数恒为0和仅比较指针的弱证据，拒绝把限制文档当完成。
- 局限：多个建议仍是宽清单，响应受到重试与长调查影响；及时意图级纠偏未证明对齐人工。不得将“持续工具调用”称为及时持续观察。
- model_output成功返回用量累计input 20,921,774、output 26,865；不包含未记录失败调用或独立维护用量，非总账单/完整成本。无最终效果裁决、不得宣布候选晋级。

## 保存与状态

中断恢复后核对最终trial/result.json：Agent执行15:03:01Z—16:32:13Z，89分12秒；含初始化/清理trial总89分32秒。verifier_result=null，未运行原生评价。wrapper137、round_end_seen=false和runner invalid是人工docker stop后的终止结果，不是独立证明OOM或任务模型自行崩溃。运行器自带failure_workspace归档也因容器已停止而失败；所幸停止前主动tar已保存。不能把此次报告中的archive_status=failed误解为全部现场丢失，也不能宣称末时刻工作区完整静止归档。宿主PID492已退出，没有重新启动。

原根见ACTIVE_WORKING_FYNE_R1_LIVE_20260912.md，trial gmZxpLe。
停止前容器/app tar保存到 `method_discovery/artifacts/active_working_20260912/workspace.prestop.tar.gz`：83,954,535 bytes；SHA256 D50141B7D7A8896C91ABCD0113DB103CC106F28BAF112703B1688574621273C1。
该tar在任务尚活动时制作，不声称事务一致或最终静止快照；原始绑定轨迹另保留。tar后docker stop定向停止main，随后docker ps -a按gmzxple过滤已无该题容器，说明runner已进入清理。未手工删除归档、旧题或镜像。

下一步先审计控制/时效与容量生命周期，不自动重跑、不因故障恢复就继续原候选队列。用户明确期待纠偏后持续读取最新意图、针对具体谬误及时打断，确认恢复后再静默；后续报告应逐条以读取/决定/送达/后续行为时间证明，而不是拿工具数替代。
