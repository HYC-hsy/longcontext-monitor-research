# 持续调查容量修复

目标：修复 active-working Fyne R1 在未结束 review 内无法回收历史、后续 wake 重复膨胀的阻塞，不改变研究判断、调度、工具或语义状态格式。

provider.py 复用现有 canonical tool_use/tool_result 配对、同模型 continuation 和原文归档。退休边界从完整 review 改为完整工具交换；并行批次所有回执闭合后才可切分，签名/加密 reasoning 与 assistant 消息同存同退，不拆改。至少保留最新交换及未完成交换；续接仍保存未解决疑问、实际采纳与根任务，结束 exchange 不代表问题解决。

容量、归档或交接无法恢复时，以 HistoryCapacityError 继承已有终止恢复异常。runtime 现有异常分支结束该监察 worker，不再靠新 wake 继续追加；普通任务不因压缩进入同步等待，完成边界仍 fail closed。原文保持于历史或精确归档，不能把此终止称为正常静默。异常原因链保留。

验证：85项 provider/agent/continuation/working-context/runtime 回归通过。新7项覆盖长未结束调查、并行批次与 reasoning、未完成调用、交接失败保留、单个不可退休超长交换、过大续接不替换历史、重复交接无副本累积。旧两整review保留断言更新为新协议交换契约；失败测试仍检查原历史/原笔记不丢，不以删除失败测试恢复通过。

真实历史结构探针：gmZxpLe audit/provider_history.json，原188项/895018 UTF-8 bytes，77个完整交换边界；新逻辑移出108项，保留续接及尾部81项/425427 bytes。原文件未修改；续接采用显式 OFFLINE STRUCTURAL PROBE 占位，归档为内存夹具，不调用模型，不是压缩语义质量或方法效果证据。原文件 SHA256 的规范化 history_measure 值为0c960c175287d5aabeb9da2fd2a22b303f2e5d508b2afe2b4043618fbe306c38。

单步代码增删：provider 78，旧测试14，新测试约110，合计小于600。没有抄入第三方框架：此处是当前 provider 协议的缺陷修复，直接复用现有配对与交接原语；PMA不使用该持续History，DPT不具有相同provider协议，不应为复用而伪装替代。

限制：现有容量指标字段仍叫characters但实际计UTF-8 bytes，新增transform明确单位。它不是精确模型token估计；维护请求也有成本；巨大单条非工具内容仍可显式失败。没有承诺任意无限长度均可恢复。没有真实模型实验。
