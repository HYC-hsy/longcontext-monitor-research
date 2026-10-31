"""Mock-only request, selector response and task-request assembly."""
import json
from contract import SYSTEM_PROMPT, freeze, model_input, dispatch, delivery_json, diagnostic_json

records = [{'id': 'G2ng7ij2', 'revision': 'rev_0985b131',
            'category': 'gap', 'content': '尚需验证边界。\n'}]
snapshot = freeze('request-1', 'cycle-1', 'task-hash-1', '完成原任务。\n',
                  records, '进行中', ['读取文件', '执行检查'])
selector_request = {'system': SYSTEM_PROMPT, 'input': model_input(snapshot)}
# No provider call: a fixed mock completion is associated with its request.
mock_completion = '<intervene>TASK,M1</intervene>'
result = dispatch(mock_completion, snapshot, completion_call_id='request-1',
                  active_cycle='cycle-1', active_task_version='task-hash-1',
                  active_records={item.id: item for item in snapshot.items})
assert result.kind == 'intervention'
assert result.blocks[-1][-1] == records[0]['content']
# Store diagnostic_json(result) only in host logs, never in the Task request.
host_diagnostic = json.loads(diagnostic_json(result))
mock_task_request = {}
payload = delivery_json(result)
if payload is not None:
    mock_task_request['reminder'] = json.loads(payload)
print(json.dumps(mock_task_request, ensure_ascii=True))
