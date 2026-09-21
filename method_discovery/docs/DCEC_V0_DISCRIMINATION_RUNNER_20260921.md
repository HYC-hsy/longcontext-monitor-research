# DCEC-v0 判别实验执行层

## 当前状态

本执行层基于机制实现提交 `1cd7048c5742ca7415937ec5142cc28fd2bcaf22`。DCEC-v0 的
state/update/control 设计未被修改。四份记录尚未执行，manifest 中
`execution_authorized=false`；本轮只完成无网络 materialization、production-request 防泄漏检查和
preflight。

## 唯一入口

```powershell
python method_discovery/run_dcec_v0_discrimination.py
```

默认命令只执行 dry-run/preflight，不建立真实 provider 连接。输出位于
`method_discovery/runs/dcec_v0_preflight_1cd7048_r2_20260921/`。真实执行入口虽已接线，但在 manifest 仍为
`execution_authorized=false` 时会在创建 provider 前拒绝：

```powershell
python method_discovery/run_dcec_v0_discrimination.py --execute
```

不得通过临时改内存对象或环境变量绕过这一版本化门禁。最终 launch audit 通过后，应先形成新的明确
授权提交，再按冻结顺序仅运行一次。

## 冻结执行语义

四份记录固定为：latent/ordinary、latent/DCEC、correct/DCEC、correct/ordinary。研究名称只存在于
runner 的研究记录；模型可见工作目录始终使用 `record-XX` / `execution-slot` 等不含条件语义的路径。

每份记录从独立、空白的 task/workspace/monitor 开始。同一 variant 的 ordinary 与 DCEC 初始 task
文件和公开事件必须逐文件哈希相同。Task Agent 是确定性 fixture，不调用模型；Supervisor 使用已解析
的 `claude_monitor_opus48`。

初始 A 为错误实现。只有 Supervisor 实际发出第一条 intervention，runner 才执行预注册 A repair：

1. 原样保存 intervention；
2. 将 workspace 切换到该 variant 的冻结 post-repair 文件；
3. 追加普通 Task Agent repair claim；
4. 不注入 `A is verified` 或研究者写好的 direct-observation 结论。

runner 不判断 intervention 语义是否正确；该事实留给离线研究审计。若没有 intervention，记录以
`mechanism_sequence_failure` 结束，不由研究者代做修复，也不进入 B/root 阶段。

## 输入隔离

runner 用显式白名单从 fixture 构造：原题、当前 variant 的真实源码、普通 Task Agent 消息和公开事件。
`research_only`、variant 名、expected label、已知 B 缺陷和评价文本不会复制到模型可读目录，也不会
进入 system/messages/tools。防泄漏回归截获 production provider 发送边界前的完整语义请求，并验证：

- 只改变研究元数据时请求 deep-equal；
- 隐藏研究对象既不在请求里，也不在 task 可读文件清单里；
- 相同初始状态下 ordinary 与 DCEC 的差异只能由已审计的 DCEC system contract 和 bounded active
  view 解释。

## 状态与成本留档

真实执行时，每个正常请求前保存 working-state SHA256、active-view SHA256/字符数；另存
`dcec_state_mutation`、所有 working.md 的 write/patch 操作、continuation 前后 SHA256。状态哈希变化若
不能由成功写操作、DCEC mutation 或 continuation 解释，标为 `out_of_band_state_change`，不自动判定
为机制错误。

每份记录还保存完整 audit、provider history、usage、request attempts、抽取的 transport 事件、最终
workspace、逻辑调用数和 Supervisor wall time。transport retry 与 logical call 分开。

## 确定性验收

执行层专用回归：

```powershell
$env:PYTHONPATH='E:\LongContext\GenericAgent-main'
python -m pytest tests/test_monitor_dcec.py tests/test_dcec_discrimination_runner.py -q
```

本轮实测 `29 passed`。pytest 退出时出现的旧临时目录权限 atexit 提示不属于测试失败。Harbor adapter
历史 `536 lines vs <525` 断言未修改；它在设计父基线同样失败，且不经过本 runner。

## 尚未做

- 未调用任何模型 API；
- 未运行四份判别记录；
- 未对结果打分；
- 未修改 DCEC prompt、生命周期、4000字符 active view、工具或 continuation；
- 未启用历史候选。
