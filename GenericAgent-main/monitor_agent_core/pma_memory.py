"""PMA phase-one maintenance adapted to a persistent, tool-using monitor.

The author owns bank operations/prompts/retrieval. This adapter owns transport,
public input selection, persistence and delivery to our existing review loop.
It deliberately does NOT run PMA's text-only reminder phase or task scheduler.
"""
from collections import deque
from dataclasses import asdict
import json
import time

from .vendor.pma_memory.memory_agent import MemoryAgent, BANK_TOOLS, PHASE1_SYSTEM
from .vendor.pma_memory.universal_memory import UniversalMemory


def public_content(value):
    """Never recycle provider reasoning/signatures as task evidence."""
    if isinstance(value, list):
        return [public_content(v) for v in value
                if not isinstance(v, dict) or v.get('type') not in
                {'thinking', 'redacted_thinking', 'openai_item'}]
    if isinstance(value, dict):
        return {k: public_content(v) for k, v in value.items()
                if k not in {'signature', 'encrypted_content'}}
    return value


class PMAMemoryMaintenance:
    def __init__(self, workspace, atomic_write, audit):
        self.workspace, self.atomic_write, self.audit = workspace, atomic_write, audit
        self.path = workspace.private_root / 'pma_memory.json'
        self.memory = (UniversalMemory.from_dict(json.loads(self.path.read_text(encoding='utf-8')))
                       if self.path.exists() else UniversalMemory())
        self.author = MemoryAgent(llm=None, memory=self.memory)
        self.query = ''
        self.cycle = 0

    def observation(self, client, wake):
        task = self.workspace.resolve_read('task/original_task.txt').read_text(encoding='utf-8')
        path = self.workspace.evidence_root / 'synopsis.jsonl'
        recent = deque(maxlen=8)
        if path.exists():
            with path.open(encoding='utf-8') as stream:
                for line in stream:
                    if not line.endswith('\n'):
                        continue  # An append still in progress is not a complete event.
                    recent.append(json.dumps(json.loads(line), ensure_ascii=False))
        # Existing public dialogue, not a new generated semantic observation layer.
        # Preserve complete recent messages, and explicitly disclose omitted history.
        history, size = [], 0
        for message in reversed(client.export_history()):
            visible = json.dumps(public_content(message), ensure_ascii=False)
            if size + len(visible) > 80000:
                break
            history.append(visible)
            size += len(visible)
        history.reverse()
        return ('[Original task]\n' + task + '\n[Current wake]\n' + wake
                + '\n[Recent first-layer synopsis; not full evidence]\n' + '\n'.join(recent)
                + '\n[Recent public monitor dialogue; older or oversized messages omitted; '
                'claims and prior conclusions are not independent proof]\n' + '\n'.join(history))

    def update(self, client, wake, review_id):
        started = time.time()
        observation = self.observation(client, wake)
        self.query = observation
        self.cycle += 1
        prompt = self.author._build_phase1_prompt(observation, step_count=self.cycle)
        before = self.memory.to_dict()
        record = dict(maintenance_id=review_id, started_at=started, before=before,
                      prompt=prompt, status='failed')
        history, system = client.export_history(), client.system
        hooks = {name: getattr(client, name, None) for name in
                 ('prepare_active_context', 'prepare_continuation', 'archive_continuation_history')}
        usage_start = len(getattr(client, 'usage_records', []))
        attempt_start = len(getattr(client, 'request_attempts', []))
        try:
            # Same provider/config/cancellation handle; temporary PMA phase context.
            # The persistent investigation history is restored even on failure.
            client.restore_history([])
            for name in hooks:
                setattr(client, name, None)
            response = client.complete([
                {'role': 'system', 'content': PHASE1_SYSTEM},
                {'role': 'user', 'content': prompt}], BANK_TOOLS)
            record['response'] = response.content
            record['usage'] = response.usage
            record['calls'] = [dict(name=c.name, arguments=c.arguments) for c in response.tool_calls]
            operations = self.author._execute_tool_calls(response)
            record['operations'] = [asdict(op) for op in operations]
            if any(not op.success for op in operations):
                raise RuntimeError('PMA memory operation failed; see maintenance audit')
            # Unknown structured calls must not silently count as successful maintenance.
            known = {t['function']['name'] for t in BANK_TOOLS}
            if any(c.name not in known for c in response.tool_calls):
                raise RuntimeError('Unrecognized PMA memory tool')
            self.atomic_write('pma_memory.json', json.dumps(self.memory.to_dict(), ensure_ascii=False))
            record['status'] = 'updated' if operations else 'no_operations'
        except Exception as exc:
            record['error_type'] = type(exc).__name__
            # Failed batches leave the last durable bank intact, with attempted ops audited.
            self.memory = UniversalMemory.from_dict(before)
            self.author.memory = self.memory
            raise
        finally:
            for item in getattr(client, 'usage_records', [])[usage_start:]:
                item['monitor_phase'] = 'pma_memory_maintenance'
            for item in getattr(client, 'request_attempts', [])[attempt_start:]:
                item['monitor_phase'] = 'pma_memory_maintenance'
            client.restore_history(history)
            client.system = system
            for name, hook in hooks.items():
                setattr(client, name, hook)
            record['after'] = self.memory.to_dict()
            record['duration_seconds'] = time.time() - started
            self.audit('pma_maintenance', **record)

    def context(self):
        return ('Revisable memory from the maintenance phase. Knowledge, experience and progress '
                'are separated; entries remain model judgments, not certified evidence. '
                'Original sources and your investigation tools remain available.\n'
                + self.author._format_memory_bank(self.query))
