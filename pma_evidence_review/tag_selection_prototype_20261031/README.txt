隔离标签协议原型（Python 3.9+，标准库）

旧 pma_contract_prototype 原样保留。本目录未集成研究仓库、未调用模型、
未运行 Tasks、未安装依赖、本原型仅供发布/开发交接。测试为模拟存储/输出，不代表 provider 成功。

契约
1. freeze 在 Phase 1 及现有审核提交后由宿主原子读取。committed 只含已提交
   项；content 是精确原始正文，不是带来源摘录/绑定 metadata 的 display。
2. TASK 代表完整原任务。M1、M2…按输入存储顺序确定性分配，映射到冻结的
   native opaque ID/revision/category/content；它们是周期选择别名，不是持久 ID。
   catalogue/model_input 返回新容器，状态与最近八步放在单独的 judgment context。
   轨迹由调用方传入“可见步骤”序列，取末八项，不把工具内部事件自行算成步骤。
   committed 和 visible_steps 必须是非字符串/bytes 的 Sequence（如 list/tuple）；
   拒绝 None、映射、集合、迭代器等无明确序列契约输入，不把字符串拆成单步字符。
   已在近期看到的内容，若行为仍与其矛盾，仍可选；不因近期出现就排除。
3. 输出只能是 <intervene>TASK,M1</intervene>（有序非空列表）或
   <no_intervention/>。别名两侧空白可忽略，拼写内部空白不可接受。
   可在 trim 外侧空白后有一个完整外层 Markdown 围栏：无 label、xml、text；
   opening/closing fence 各独占一行。拒绝其他 label、部分/多个/嵌套围栏，
   围栏外正文，属性、额外/冲突/嵌套标签、正文、未知/重复/空别名和旧 JSON。
   宿主 diagnostic_json 保留 raw_output、normalized、normalized_output 和 error；
   trim 或移除完整围栏算 normalized；未成功规范化时 normalized_output 为 null。
   不改写模型内容；无正文摘要、理由、版本/哈希抄写。错误无部分 blocks。
4. dispatch 要求宿主 completion_call_id 对应捕获的 snapshot，且 active cycle、
   task version 相同；所选 memory 必须仍在活库且完整 Item 身份相等。
   revision/content/category 改动或删除均 stale_selection，不替换新版内容。
   未选条目变化不影响选择；no_intervention 也检查周期/任务版本。
   这取代旧原型“同周期可发送删除/修改前内容”的政策。
5. 必须在同一锁/事务/CAS下验证并入队。active_records 是宿主当前 committed
   Item 映射。任务文本变化要更换 task_version，周期失效要更换 cycle。
   call_id 每次请求唯一，宿主保存 request->snapshot 关联，不从模型输出取它。
   M1 字符串本身不能认证调用来源：如果调用方把旧结果错误标为新 call，任何
   纯标签解析器都无法识别。这里检查可信宿主关联，不宣称用标签解决认证。
6. delivery_json 只为 intervention 返回含所选 blocks 的 Task payload JSON；
   不含 raw/normalized/error/状态/轨迹。error 和 no_intervention 返回 Python None，
   调用方不得因此发送 reminder（不是发送 JSON null 或空诊断消息）。
   diagnostic_json 仅写宿主日志，不能进入 Task request；非字符串 raw 用类型标记
   记录，不调用任意对象 repr/str，不尝试 JSON 序列化原对象。
   ensure_ascii=True 使 surrogate 等字符串也能 UTF-8 编码，解码精确保留原文。
   error/no_intervention/intervention 独立。隐藏 gap 不删除、不关闭它。
   不新增容量限制；真实上游限制由集成保留并明确报错，不静默截断。

运行
  cd pma_tag_selection_prototype
  python3 -m unittest -v
  python3 mock_example.py
实际本地结果：14 tests，OK（版本以发布验证记录为准）。测试不证明语义收益或所有工程问题消失。

给开发线程的指令
基于 production af4a26e1ec91656a5fe1c333f9c12ca0e5fde897，只改 selector prompt、
输出协议、宿主快照/别名映射及原文装配。冻结 Phase 1、reviewer prompt/逻辑、
selected-evidence、repair/admission、gap 规则与调度。二阶段输入为原任务、已提交
带编号库、最近八步可见轨迹和状态。仅 TASK 和 M 别名可选。native ID/revision
保持 opaque 字符串，原文来自 content。不要增加 planner、Ambient 或反馈循环。

在 Task 实验前新增并执行实际 real-client smoke：真实 selector 请求经过实际
parser 和实际 Task-request assembly，必须至少取得一次成功 intervene，并核对
所选 source content 与装配后的原文 identity。仅 no_intervention/静默的负例不能
证明交付链路。记录 request 关联、raw/normalized、解析结果、引用与正文核对；
smoke 成功与效果评估分开记录。此隔离原型没有执行 smoke。

未处理：已提交语义错误、整理遗漏和 selector 选择质量。真实集成须验证原子读取、
调用关联、锁和真实 transport。别名不是安全沙箱，已审核正文仍可能包含指令文本。
