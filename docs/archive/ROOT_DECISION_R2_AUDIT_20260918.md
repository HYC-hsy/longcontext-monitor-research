# Root decision R2：真实运行审计

Run: `clean-monitor-fyn-2.2.0-roadmap-root-decision-20260917-r2`

## 结果

- 任务阶段正常结束，未出现 Harbor 或 provider 异常。
- 原生评价：`2 / 7`，reward `0.2727272727`。
- 监察者实际完成 10 次 review、70 次 provider 请求；两次上下文续接均提交成功，其中第二次先出现 `unexpected_tool`，随后完成一次格式修复。
- 监察者发出 1 次实际纠偏，任务方随后补做了 Target 4、5 的部分缺口。

## 根判断实际行为

根交接时确实选中了 `decision_contract`，并读取了最近任务轨迹，检查了验证器文件名，运行了
`go build ./...`，随后读取了 `data/validation/string.go`。然而它没有运行完整的公开测试，也没有覆盖
Target 1–7 的逐项证据。它看到了 `NewAllStrings` 的函数签名与原任务不一致，却把文件名/实现偏差降为
不影响功能的小问题，仍调用 `allow_complete`。

原任务要求的签名是：

`NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator`

实际文件是：

`NewAllStrings(itemValidator fyne.StringValidator) func([]string) error`

事后验证显示还存在多项未满足项：Target 1、2、4、6、7 的测试构建失败，Target 6 的行为测试失败；
只有 Target 3 和 Target 5 在该评价阶段通过。因此“编译通过 + 局部函数存在”被错误扩大成全局完成。

## 诊断

本次失败不是续接工程故障，也不是根合同开关没有接入。它是一个错误闭合：维护 bank 反复保存
“7 targets complete”，根判断虽重新看到原任务和公开证据，仍围绕该结论做局部确认。新的 decision
提示没有强制形成覆盖范围与证据范围的对应关系。

这组结果只评价 decision 候选在该题上的一次运行；simple 对照必须使用同一源码、题目、隔离配置和新
run-id，不能把 R2 单组结果解释为候选优劣。
