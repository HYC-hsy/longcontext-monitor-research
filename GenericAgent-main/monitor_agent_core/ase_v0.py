"""ASE-v0 request-local representation and mechanical control continuity.

No task semantics, requirement extraction, or additional model stage live here.
"""

from __future__ import annotations

import hashlib
import json

from .dcm_v0 import DecisionMeasurementBoundary


ASE_REFERENCE_MAX_CHARS = 16000
REFERENCE_LIMIT = ASE_REFERENCE_MAX_CHARS  # Historical import name; the limit is on source text.
CONTINUITY_LIMIT = 1400
ANCHOR_LIMIT = 260
FOLLOW_LIMIT = 160
RATIONALE_LIMIT = 180
META_FOLLOW_CYCLE_THRESHOLD = 2  # Experimental display threshold, not a task judgment.

SYSTEM_PROMPT = """You are the persistent Curator-Supervisor of a long-running Task Agent. The full public task at task/original_task.txt is the authority.

At initialization, read the public task and inspect the initial workspace as needed, then create monitor/reference.md as your Task Book. Keep only durable task cognition that may matter again much later: important requirements and constraints, stable facts learned from public evidence, and distinctions whose loss could cause a consequential mistake to recur. Preserve enough context to remember what a learned entry actually supports and when it may need rechecking. The Task Book is your revisable interpretation, not verified truth or current-world proof. Revise or delete it when public evidence undermines it. Do not use it as a progress or completion ledger.

On each review, first orient to the Task Agent's current consequential move. Ask whether some still-relevant durable cognition would change that move if it were properly considered. If so, reactivate the relevant context. If no existing Task Book entry resolves the issue but the move depends on an unresolved premise whose truth could change your control action, investigate that premise with the ordinary tools. When investigation produces a durable fact or distinction that may matter again, update the Task Book. Do not investigate merely because something is unknown.

Your default is silence. Intervene when restoring relevant task cognition has control value. Prefer exposing the forgotten requirement, contradicted premise, learned distinction, or evidential limitation over prescribing implementation. The Task Agent owns implementation, debugging, test construction, and experimentation.

A Task Book entry, prior conclusion, passing observation, or previous reminder is evidence only for what it actually supports now. New feedback may show that the Task Agent is wrong, that your earlier reminder was wrong, or that a stored belief needs revision. Reconsider your own cognition accordingly.

When a Control Echo is present, it identifies the most recent reminder that was actually delivered to the Task Agent and whose first genuine feedback is now being assessed. It is prior control context, not an open concern or task truth. Use the fresh feedback to decide again. Once the Agent has recovered the relevant understanding and is autonomously pursuing a sound direction, withdraw and let it work; the implementation need not be finished before local supervision ends.

At whole-task completion, return to the complete authoritative mission rather than the most recent local repair. Consider whether any still-valid requirement, learned fact, distinction, or unresolved action-changing premise would change the release decision. Investigate only where resolving uncertainty could change control. Do not require omniscience, and do not treat the absence of a remembered defect as proof of completion.

Use the seven ordinary tools directly. monitor/working.md remains private scratch and compaction-continuation compatibility, not a second Task Book. Provider History is conversational continuity, not authority. Task evidence is read-only under task/; private files are writable under monitor/. code_run starts in monitor/ and is not a filesystem sandbox."""

RELEASE_GUIDANCE = (
    'This proposed release has not executed. Your current task reference, recent situation and prior '
    'conversational evidence remain available. Reconsider freely: use ordinary tools, change the control '
    'action, or repeat the same kind of release in a new model turn if it remains appropriate.'
)


def digest(value):
    return hashlib.sha256(str(value).encode('utf-8')).hexdigest()


def excerpt(value, limit):
    value = str(value or '').strip()
    return value[:limit] + (' [excerpt truncated]' if len(value) > limit else '')


def reference_surface(workspace, limit=REFERENCE_LIMIT):
    """Expose every accepted reference character; never select a positional excerpt."""
    if type(limit) is not int or limit < 1:
        raise ValueError('ASE reference source limit must be a positive integer')
    try:
        source = workspace.resolve_read('monitor/reference.md').read_bytes()
        try:
            content = source.decode('utf-8')
        except UnicodeDecodeError:
            content, status = '', 'invalid_utf8'
        else:
            status = 'present' if content.strip() else 'empty'
    except FileNotFoundError:
        source, content, status = b'', '', 'absent'
    except (OSError, ValueError) as exc:
        source, content, status = b'', '', 'unavailable:' + type(exc).__name__
    header = ('Task Book — your own durable, revisable task cognition; not verified truth, progress, '
              'or current-world proof. '
              'The full public task at task/original_task.txt remains authoritative.\n')
    footer = '\nSource: monitor/reference.md.'
    if status == 'present' and len(content) > limit:
        status = 'oversized'
    if status == 'oversized':
        body = (f'[Reference oversized: {len(content)} source characters exceed the {limit}-character '
                'full-exposure boundary. No excerpt or summary was substituted. '
                'Use file_read and compress your private reference.]')
        truncated, visible = False, ''
    elif status != 'present':
        body = (f'[Reference {status}; no task interpretation was generated by the runtime. '
                f'The full reference must be at most {limit} source characters.]')
        truncated, visible = False, ''
    else:
        body, visible, truncated = content, content, False
    rendered = header + body + footer
    return rendered, {
        'path': 'monitor/reference.md', 'status': status,
        'limit_characters': limit, 'source_characters': len(content),
        'visible_characters': len(visible), 'truncated': truncated,
        'source_sha256': hashlib.sha256(source).hexdigest(),
        'rendered_characters': len(rendered),
        'rendered_utf8_bytes': len(rendered.encode('utf-8')),
    }


class LocalContinuity:
    """One local episode: last submitted intervention plus latest follow expectation."""

    def __init__(self, audit, *, meta_regulation=False):
        self.audit = audit
        self.meta_regulation = meta_regulation
        self.anchor = None
        self.follow = None
        self.review_id = None
        self.last_output = None
        self.last_call = None
        self.pending_surface = None
        self.follow_count = 0
        self.episode_start_turn = None
        self.latest_intervention_turn = None
        self.intervention_count = 0
        self.completed_follow_cycles = 0
        self.follow_pending = False
        self.file_read_count = 0
        self.code_run_count = 0
        self.duplicate_count = 0
        self.observation_identities = {}
        self.observation_trace = []
        self.pending_observations = {}
        self.reorientation_announced = False
        self.current_task_turn = None

    def begin_review(self, review_id, task_turn=None):
        self.review_id = review_id
        self.current_task_turn = task_turn
        if self.anchor is not None and self.follow_pending:
            self.completed_follow_cycles += 1
            self.follow_pending = False
            self.audit('ase_follow_feedback_cycle_completed',
                       completed_follow_cycles=self.completed_follow_cycles,
                       task_turn=task_turn)
        if self.active:
            age = (task_turn - self.episode_start_turn
                   if isinstance(task_turn, int) and isinstance(self.episode_start_turn, int) else None)
            self.audit('ase_control_episode_observed', task_turn=task_turn,
                       episode_start_task_turn=self.episode_start_turn,
                       latest_intervention_turn=self.latest_intervention_turn,
                       episode_task_turn_age=age, intervention_count=self.intervention_count,
                       completed_follow_cycles=self.completed_follow_cycles,
                       file_read_count=self.file_read_count, code_run_count=self.code_run_count,
                       exact_duplicate_count=self.duplicate_count,
                       recent_observation_trace=self.observation_trace[-4:])
            if self.completed_follow_cycles >= META_FOLLOW_CYCLE_THRESHOLD:
                self.audit('ase_meta_regulation_eligible', task_turn=task_turn,
                           completed_follow_cycles=self.completed_follow_cycles,
                           threshold=META_FOLLOW_CYCLE_THRESHOLD,
                           exposure_enabled=self.meta_regulation,
                           first=not self.reorientation_announced)
                self.reorientation_announced = True
        self.last_output = None
        self.last_call = None
        self.pending_surface = None

    @property
    def active(self):
        return self.anchor is not None

    def observe(self, record, line):
        if record.get('review_id') != self.review_id:
            return
        locator = f'monitor/audit/dialogue.jsonl#{line}'
        if record.get('event') == 'model_output' and str(record.get('content') or '').strip():
            self.last_output = {'text': record['content'], 'locator': locator,
                                'model_turn': record.get('turn')}
        elif record.get('event') == 'tool_call':
            try:
                args = json.loads(record.get('arguments') or '{}')
            except (TypeError, ValueError):
                args = {}
            self.last_call = {'name': record.get('name'), 'args': args,
                              'locator': locator, 'model_turn': record.get('turn')}
            if self.active and record.get('name') in {'file_read', 'code_run'}:
                name = record['name']
                if name == 'file_read':
                    identity = json.dumps({key: args.get(key, default) for key, default in (
                        ('path', None), ('start', 1), ('count', 200), ('tail', False),
                        ('offset', 0), ('max_chars', 20000))}, sort_keys=True)
                    self.file_read_count += 1
                    item = {'kind': name, 'path': excerpt(args.get('path'), 100),
                            'range_sha256': digest(identity),
                            'start': args.get('start', 1), 'count': args.get('count', 200),
                            'offset': args.get('offset', 0), 'locator': locator}
                else:
                    identity = str(args.get('code') or '')
                    self.code_run_count += 1
                    item = {'kind': name, 'command_sha256': digest(identity),
                            'command_excerpt': excerpt(identity, 100), 'locator': locator}
                key = (name, identity)
                prior = self.observation_identities.get(key, 0)
                self.observation_identities[key] = prior + 1
                if prior:
                    self.duplicate_count += 1
                item['exact_duplicate_count'] = prior
                self.observation_trace.append(item)
                self.observation_trace = self.observation_trace[-4:]
                tool_id = record.get('tool_id')
                if tool_id:
                    self.pending_observations[tool_id] = item
                self.audit('ase_episode_observation', **item,
                           file_read_count=self.file_read_count,
                           code_run_count=self.code_run_count,
                           episode_exact_duplicate_count=self.duplicate_count)
        elif record.get('event') == 'tool_result':
            item = self.pending_observations.pop(record.get('tool_id'), None)
            if item is not None:
                result = record.get('data')
                if isinstance(result, dict):
                    item['status'] = result.get('status')
                    item['exit_code'] = result.get('exit_code')
                self.audit('ase_episode_observation_result', kind=item['kind'],
                           call_locator=item['locator'], result_locator=locator,
                           status=item.get('status'), exit_code=item.get('exit_code'))

    def submitted_intervention(self, message, task_turn=None):
        call, rationale = self.last_call or {}, self.last_output or {}
        if self.anchor is None:
            self.episode_start_turn = task_turn
            self.intervention_count = 0
            self.completed_follow_cycles = 0
            self.file_read_count = self.code_run_count = self.duplicate_count = 0
            self.observation_identities.clear()
            self.observation_trace.clear()
            self.pending_observations.clear()
            self.reorientation_announced = False
            self.audit('ase_control_episode_started', task_turn=task_turn)
        self.anchor = {'message': excerpt(message, ANCHOR_LIMIT), 'message_sha256': digest(message),
                       'rationale': excerpt(rationale.get('text'), RATIONALE_LIMIT),
                       'rationale_locator': rationale.get('locator'),
                       'action_locator': call.get('locator'), 'review_id': self.review_id}
        self.follow = None
        self.follow_pending = False
        self.intervention_count += 1
        self.latest_intervention_turn = task_turn
        self.audit('ase_continuity_updated', source='intervene', anchor=self.anchor,
                   task_turn=task_turn, intervention_count=self.intervention_count,
                   episode_start_task_turn=self.episode_start_turn,
                   completed_follow_cycles=self.completed_follow_cycles)

    def completed_wait(self, action, task_turn=None):
        if action.kind != 'wait':
            return
        call, rationale = self.last_call or {}, self.last_output or {}
        mode = action.payload.get('mode')
        if mode == 'patrol':
            prior = self.active
            if prior:
                self.audit('ase_control_episode_ended', task_turn=task_turn,
                           episode_start_task_turn=self.episode_start_turn,
                           intervention_count=self.intervention_count,
                           completed_follow_cycles=self.completed_follow_cycles,
                           file_read_count=self.file_read_count,
                           code_run_count=self.code_run_count,
                           exact_duplicate_count=self.duplicate_count)
            self.anchor = self.follow = None
            self.follow_count = 0
            self.episode_start_turn = None
            self.latest_intervention_turn = None
            self.intervention_count = self.completed_follow_cycles = 0
            self.follow_pending = False
            self.file_read_count = self.code_run_count = self.duplicate_count = 0
            self.observation_identities.clear()
            self.observation_trace.clear()
            self.pending_observations.clear()
            self.reorientation_announced = False
            self.audit('ase_continuity_cleared', source='wait_patrol', had_active=prior,
                       action_locator=call.get('locator'), task_turn=task_turn)
        elif mode == 'follow':
            if not self.active:
                self.audit('ase_follow_without_episode', task_turn=task_turn,
                           requested_after_turns=action.payload.get('after_turns'))
                return
            reason = rationale.get('text')
            self.follow = {'reason': excerpt(reason, FOLLOW_LIMIT),
                           'reason_sha256': digest(reason),
                           'rationale': excerpt(rationale.get('text'), RATIONALE_LIMIT),
                           'action_locator': call.get('locator'), 'review_id': self.review_id}
            self.follow_count += 1
            self.follow_pending = True
            age = (task_turn - self.episode_start_turn
                   if isinstance(task_turn, int) and isinstance(self.episode_start_turn, int) else None)
            self.audit('ase_continuity_updated', source='wait_follow', follow=self.follow,
                       anchor_locator=self.anchor.get('action_locator') if self.anchor else None,
                       follow_count=self.follow_count, task_turn=task_turn,
                       episode_task_turn_age=age,
                       requested_after_turns=action.payload.get('after_turns'))

    def render(self):
        if not self.active:
            self.pending_surface = None
            return None
        lines = ['Local Control Continuity — your prior action, not task truth.']
        if self.anchor is not None:
            lines.append('Previous intervention: ' + self.anchor['message'])
            if self.anchor['rationale']:
                lines.append('Prior rationale: ' + self.anchor['rationale'])
            lines.append('Source: ' + str(self.anchor['action_locator'] or 'unavailable'))
        if self.follow is not None:
            if self.follow['reason']:
                lines.append('Currently awaiting: ' + self.follow['reason'])
            elif self.follow['rationale'] and self.anchor is None:
                lines.append('Follow context: ' + self.follow['rationale'])
            lines.append('Follow source: ' + str(self.follow['action_locator'] or 'unavailable'))
        if self.meta_regulation:
            age = None
            if isinstance(self.episode_start_turn, int) and isinstance(self.current_task_turn, int):
                age = max(0, self.current_task_turn - self.episode_start_turn)
            lines.append(f'Control episode: age={age if age is not None else "unknown"} task turns; '
                         f'interventions={self.intervention_count}; completed follow cycles={self.completed_follow_cycles}; '
                         f'observations={self.code_run_count} code runs / {self.file_read_count} file reads; '
                         f'exact duplicates={self.duplicate_count}.')
            if self.completed_follow_cycles >= META_FOLLOW_CYCLE_THRESHOLD:
                lines.append('Control Reorientation: this local control has crossed multiple Task feedback cycles. '
                             'Reconsider whether the current observation still changes your control decision. '
                             'You may change measurement or your premise, continue intervention, or return to broader patrol; '
                             'neither continuation nor release is required.')
        lines.append('Current public feedback may confirm, revise, or invalidate this local concern.')
        trace = self.observation_trace[-4:] if self.meta_regulation else []
        content = '\n'.join(lines + (['Recent Supervisor observations (mechanical): ' +
                                      json.dumps(trace, ensure_ascii=False, separators=(',', ':'))]
                                     if trace else []))
        while len(content) > CONTINUITY_LIMIT and trace:
            trace = trace[1:]
            content = '\n'.join(lines + (['Recent Supervisor observations (mechanical): ' +
                                          json.dumps(trace, ensure_ascii=False, separators=(',', ':'))]
                                         if trace else []))
        if len(content) > CONTINUITY_LIMIT:
            raise ValueError('ASE continuity surface exceeded its bound')
        self.pending_surface = {'content': content, 'sha256': digest(content),
                                'anchor_locator': self.anchor.get('action_locator') if self.anchor else None,
                                'follow_locator': self.follow.get('action_locator') if self.follow else None,
                                'meta_regulation': self.meta_regulation,
                                'meta_eligible': self.completed_follow_cycles >= META_FOLLOW_CYCLE_THRESHOLD,
                                'meta_trace_count': len(trace)}
        return content

    def surface_visible(self):
        shown, self.pending_surface = self.pending_surface, None
        if shown is not None:
            self.audit('ase_continuity_surface_injected', **shown,
                       rendered_characters=len(shown['content']))
            if shown['meta_regulation']:
                self.audit('ase_meta_regulation_surface_injected',
                           rendered_characters=len(shown['content']),
                           surface_sha256=shown['sha256'],
                           eligible=shown['meta_eligible'],
                           trace_count=shown['meta_trace_count'],
                           source_locator=shown['anchor_locator'])
        return shown



class ControlEcho:
    """One delivery-confirmed reminder for one genuine-feedback rejudgment."""

    MESSAGE_LIMIT = 2000

    def __init__(self, audit):
        self.audit = audit
        self.pending_submission = None
        self.active_echo = None
        self.review_id = None
        self.pending_surface = None
        self.last_intervene_call_locator = None
        self.visible_review_id = None

    @property
    def active(self):
        return self.active_echo is not None

    def begin_review(self, review_id):
        self.review_id = review_id
        self.pending_surface = None
        self.last_intervene_call_locator = None
        self.visible_review_id = None

    def observe(self, record, line):
        if (record.get('review_id') == self.review_id and record.get('event') == 'tool_call'
                and record.get('name') == 'intervene'):
            self.last_intervene_call_locator = f'monitor/audit/dialogue.jsonl#{line}'

    def note_submission(self, message, receipt):
        submission_id = receipt.get('submission_id') if isinstance(receipt, dict) else None
        if not submission_id:
            raise ValueError('An intervention submission needs a mechanical identity')
        self.pending_submission = {
            'submission_id': submission_id, 'message': message,
            'message_sha256': digest(message),
            'submitted_task_turn': receipt.get('submitted_task_turn'),
            'submitted_cursor': receipt.get('submitted_cursor'),
            'action_locator': self.last_intervene_call_locator,
        }
        self.audit('curator_echo_submission_pending', **self.pending_submission)

    def reconcile_receipt(self, receipt):
        pending = self.pending_submission
        if pending is None or receipt.get('submission_id') != pending['submission_id']:
            self.audit('curator_echo_receipt_stale', submission_id=receipt.get('submission_id'),
                       delivered=receipt.get('delivered'))
            return 'stale'
        self.pending_submission = None
        if not receipt.get('delivered'):
            self.audit('curator_echo_delivery_failed', submission_id=pending['submission_id'],
                       error_type=receipt.get('error_type'))
            return 'failed'
        self.active_echo = dict(pending, delivery_kind=receipt.get('delivery_kind'),
                                delivered_task_turn=receipt.get('delivery_task_turn'),
                                delivered_cursor=receipt.get('delivery_cursor'))
        self.audit('curator_echo_delivery_confirmed', **self.active_echo)
        return 'delivered'

    def render(self):
        echo = self.active_echo
        if echo is None:
            self.pending_surface = None
            return None
        message = echo['message'][:self.MESSAGE_LIMIT]
        if len(echo['message']) > self.MESSAGE_LIMIT:
            message += '\n[Reminder excerpt truncated; read the cited delivery/audit record for full text.]'
        content = ('Control Echo — one-cycle context for the most recent reminder actually delivered '
                   'to the Task Agent.\n\nDelivered reminder:\n' + message +
                   '\n\nThis is prior control, not task truth and not an automatically open concern. '
                   'The fresh Task feedback may show uptake, continued drift, or that the reminder itself '
                   'was wrong. Reassess now. This Echo will not persist automatically after this review\'s '
                   'terminal control action.\nSource: ' + str(echo.get('action_locator') or 'unavailable') +
                   '; submission_id=' + echo['submission_id'])
        self.pending_surface = {'content': content, 'sha256': digest(content),
                                'submission_id': echo['submission_id'],
                                'source_locator': echo.get('action_locator'),
                                'message_sha256': echo['message_sha256']}
        self.audit('curator_echo_surface_prepared', **self.pending_surface)
        return content

    def surface_visible(self):
        shown, self.pending_surface = self.pending_surface, None
        if shown is not None:
            self.visible_review_id = self.review_id
            self.audit('curator_echo_surface_injected', **shown,
                       rendered_characters=len(shown['content']))
        return shown

    def complete_review(self, action):
        if action is None or action.kind == 'root_route':
            return
        if (action.kind in {'wait', 'local_intervened', 'root_intervened', 'allow_complete'}
                and self.active_echo is not None and self.visible_review_id == self.review_id):
            prior = self.active_echo
            self.active_echo = None
            self.visible_review_id = None
            self.audit('curator_echo_consumed', submission_id=prior['submission_id'],
                       terminal_action=action.kind)


class ReconsiderationBoundary(DecisionMeasurementBoundary):
    """The existing DCM mechanical two-turn boundary with shorter ASE wording."""

    def __init__(self, audit, visible_context):
        super().__init__(audit)
        self.visible_context = visible_context

    def release(self, kind, frame, arguments):
        prior = self.challenge
        self.audit('ase_release_attempted', release_kind=kind, frame=frame,
                   proposed_args=dict(arguments), visible_context=self.visible_context())
        result = super().release(kind, frame, arguments)
        if result is not None and self.challenge is not None and self.challenge is not prior:
            result = {'status': 'release_not_executed',
                      'challenge_id': self.challenge['challenge_id'],
                      'proposed_action': 'wait(mode=patrol)' if kind == 'patrol'
                                         else 'allow_complete()',
                      'proposed_reason': arguments.get('reason'), 'message': RELEASE_GUIDANCE}
            self.audit('ase_reconsideration_boundary', challenge_id=self.challenge['challenge_id'],
                       release_kind=kind, frame=frame, proposed_args=dict(arguments),
                       visible_context=self.visible_context())
        elif result is not None and self.challenge is prior:
            result = {'status': 'release_not_executed',
                      'challenge_id': prior['challenge_id'],
                      'message': 'The release remains pending a new model response; it has not executed.'}
        elif result is None and prior is not None:
            self.audit('ase_release_confirmed', challenge_id=prior['challenge_id'],
                       release_kind=kind, frame=frame, visible_context=self.visible_context())
        return result

    def next_tool(self, name, arguments):
        active = self.challenge
        super().next_tool(name, arguments)
        if active is not None and name not in {'wait', 'allow_complete'}:
            self.audit('ase_post_boundary_tool', challenge_id=active['challenge_id'],
                       tool_name=name, model_turn=self.model_turn,
                       issued_at_model_turn=active['issued_at_model_turn'],
                       task_path=arguments.get('path') if name == 'file_read' else None,
                       command_sha256=digest(arguments.get('code')) if name == 'code_run' and
                       arguments.get('code') is not None else None)

    def abandon(self, disposition):
        active = self.challenge
        super().abandon(disposition)
        if active is not None:
            self.audit('ase_release_abandoned', challenge_id=active['challenge_id'],
                       disposition=disposition)

    def end_review(self, reason):
        active = self.challenge
        super().end_review(reason)
        if active is not None:
            self.audit('ase_review_ended_with_boundary_pending',
                       challenge_id=active['challenge_id'], disposition=reason)
