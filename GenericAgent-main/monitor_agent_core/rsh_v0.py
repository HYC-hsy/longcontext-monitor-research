"""Root-release provenance from receipts actually visible in this root review.

This is a navigation surface, not a requirement or evidence-adequacy judgment.
"""

from __future__ import annotations

import json


INHERITED = (
    "Other completion support may come from persistent Supervisor History, monitor/working.md, "
    "earlier reviews, or prior local judgments. This horizon does not reclassify or invalidate "
    "that inherited support; it only distinguishes it from fresh direct task-grounded "
    "observations in this root decision."
)
RELEASE_NOTE = (
    "For this whole-task release, use the horizon only to distinguish fresh direct grounds "
    "from inherited support. A narrow fresh horizon is not automatically inadequate, and "
    "inherited support is not automatically invalid; decide whether any material contrary "
    "state remains compatible with the grounds you are actually relying on."
)
MAX_CHARS = 1800


class ReleaseSupportHorizon:
    def __init__(self, workspace, audit):
        self.workspace = workspace
        self.audit = audit
        self.active = False

    def begin(self, review_id, handoff):
        self.active = True
        self.review_id = review_id
        self.handoff = dict(handoff)
        self.calls = {}
        self.results = {}
        self.visible = {}
        self.pending_inputs = {}
        self.session_commands = {}
        self.situation = None
        self.audit('rsh_root_started', root_identity=self.handoff)

    def end(self):
        if self.active:
            self.audit('rsh_root_ended', root_identity=self.handoff,
                       visible_direct_count=len(self.visible))
        self.active = False

    @staticmethod
    def _locator(line):
        return f'monitor/audit/dialogue.jsonl#{line}'

    def observe(self, record, line):
        if (not self.active or record.get('review_id') != self.review_id
                or record.get('event', '').startswith('rsh_')):
            return
        event = record['event']
        if event == 'tool_call':
            try:
                args = json.loads(record.get('arguments') or '{}')
            except (TypeError, ValueError):
                args = {}
            self.calls[record['tool_id']] = {
                'name': record.get('name'), 'args': args,
                'call_event_locator': self._locator(line), 'turn': record.get('turn')}
        elif event == 'tool_result':
            self.results[record['tool_id']] = {
                'data': record.get('data'), 'result_event_locator': self._locator(line)}
            call = self.calls.get(record['tool_id'])
            data = record.get('data')
            if (call and call['name'] == 'code_run' and isinstance(data, dict)
                    and data.get('session_id') and call['args'].get('code')):
                self.session_commands[data['session_id']] = call['args']['code']
        elif event == 'model_input':
            self.pending_inputs[record.get('turn')] = [
                item.get('tool_use_id')
                for message in record.get('messages', [])
                for item in message.get('tool_results', [])
                if item.get('tool_use_id') in self.results]
        elif event == 'model_output':
            for tool_id in self.pending_inputs.pop(record.get('turn'), []):
                row = self._direct_row(tool_id)
                if row is not None and tool_id not in self.visible:
                    row['visible_model_output_locator'] = self._locator(line)
                    self.visible[tool_id] = row
                    self.audit('rsh_direct_observation_visible', root_identity=self.handoff,
                               **row)
        elif event == 'supervisory_situation_injected':
            locator = record.get('manifest_locator')
            if locator and not str(record.get('content', '')).startswith('Situation unchanged'):
                try:
                    path = self.workspace.resolve_read(locator)
                    manifest = json.loads(path.read_text(encoding='utf-8'))
                    changes = manifest.get('changed_paths', {})
                    self.situation = {
                        'situation_locator': self._locator(line),
                        'manifest_locator': locator,
                        'changed_path_count': sum(len(changes.get(k, []))
                                                  for k in ('added', 'modified', 'deleted')),
                        'task_code_run_rows': len(manifest.get('code_run_outcomes', [])),
                        'handoff_identity': manifest.get('root_handoff'),
                    }
                except (OSError, ValueError, KeyError):
                    self.situation = {'situation_locator': self._locator(line),
                                      'manifest_locator': locator,
                                      'status': 'manifest_unavailable'}

    def _direct_row(self, tool_id):
        call = self.calls.get(tool_id)
        result = self.results.get(tool_id)
        if not call or not result or not isinstance(result['data'], dict):
            return None
        data = result['data']
        common = {'tool_id': tool_id, 'call_event_locator': call['call_event_locator'],
                  'result_event_locator': result['result_event_locator']}
        if call['name'] == 'file_read':
            path = data.get('path') or call['args'].get('path')
            if not isinstance(path, str) or not path.replace('\\', '/').startswith('task/'):
                return None
            if data.get('status') == 'error' or 'error' in data:
                return None
            if 'content' not in data:
                return None
            return dict(common, kind='file_read', path=path.replace('\\', '/'))
        if call['name'] == 'code_run':
            status = data.get('status')
            if status not in {'success', 'error', 'completed', 'failed'}:
                return None
            command = (call['args'].get('code') or
                       self.session_commands.get(call['args'].get('session_id')) or
                       'unknown/not_available')
            return dict(common, kind='code_run', command=str(command), status=status,
                        exit_code=data.get('exit_code'))
        return None

    def snapshot(self):
        rows = list(self.visible.values())
        return {
            'root_identity': dict(self.handoff),
            'fresh_task_file_reads': [r for r in rows if r['kind'] == 'file_read'],
            'fresh_supervisor_code_runs': [r for r in rows if r['kind'] == 'code_run'],
            'fresh_original_task_read': any(r['kind'] == 'file_read' and
                                            r['path'] == 'task/original_task.txt' for r in rows),
            'full_original_task_in_root_input': True,
            'latest_full_cfs_situation': self.situation,
        }

    def render(self, challenge_id):
        facts = self.snapshot()
        identity = facts['root_identity']
        prefix = [
            'Release Support Horizon — mechanical provenance only; not a coverage or adequacy verdict.',
            f"Scope: whole-task completion; root generation={identity.get('generation')}; "
            f"request_id={identity.get('request_id')}; challenge_id={challenge_id}.",
            'Full original task was present in root input; this does not verify any requirement.',
            'Fresh original-task file_read: ' + ('yes' if facts['fresh_original_task_read'] else 'no') + '.',
        ]
        situation = facts['latest_full_cfs_situation']
        if situation is None:
            prefix.append('Latest provider-visible full CFS Situation in this root: none recorded.')
        else:
            prefix.append('Latest full CFS Situation: ' + situation['situation_locator'] +
                          '; manifest=' + situation['manifest_locator'] +
                          '; changed_paths=' + str(situation.get('changed_path_count', 'unknown')) +
                          '; Task code_run rows=' + str(situation.get('task_code_run_rows', 'unknown')) +
                          '; handoff=' + json.dumps(situation.get('handoff_identity'), ensure_ascii=False,
                                                   separators=(',', ':')))
        reads = facts['fresh_task_file_reads']
        runs = facts['fresh_supervisor_code_runs']
        prefix.append(f'Fresh root task file_read results: {len(reads)}; Supervisor code_run results: {len(runs)}.')
        suffix = '\n' + INHERITED + '\n' + RELEASE_NOTE
        lines = list(prefix)
        for row in reads + runs:
            if row['kind'] == 'file_read':
                text = f"file_read {row['path']} call={row['call_event_locator']} result={row['result_event_locator']}"
            else:
                text = (f"code_run {row['command'][:120]!r} status={row['status']} "
                        f"exit_code={row['exit_code']} call={row['call_event_locator']} "
                        f"result={row['result_event_locator']}")
            if len('\n'.join(lines + [text]) + suffix) > MAX_CHARS - 80:
                lines.append(f'Additional direct observations omitted here; full locators in rsh_horizon_emitted audit.')
                break
            lines.append(text)
        content = '\n'.join(lines) + suffix
        if len(content) > MAX_CHARS:
            raise ValueError('RSH fixed metadata exceeds bounded result')
        self.audit('rsh_horizon_emitted', challenge_id=challenge_id, **facts,
                   fresh_task_file_read_count=len(reads), fresh_code_run_count=len(runs),
                   rendered_char_count=len(content), rendered_content=content)
        return content
