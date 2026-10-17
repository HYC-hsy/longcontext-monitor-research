"""Thin GA lifecycle adapter around the unmodified released PoS BeliefManager.

This module is imported only by an isolated worker with ``vendor`` on sys.path.
The caller owns Task actions and termination; no PMA object is instantiated.
"""
from __future__ import annotations

from copy import deepcopy
import json

from belief.manager import BeliefManager
from prompts.react_prompt import FRONTIER_ACTION_SELECTION_CONTRACT, _frontier_relevant_world


def execution_config() -> dict:
    """Resolved method values from fixed configs/loca/pos.yaml, not its provider route."""
    return {
        'benchmark': 'LOCA-Bench', 'method': 'ReAct-PoS', 'harness': 'ReAct',
        'include_actions': True, 'max_json_retries': 1,
        'context': {
            'type': 'belief', 'task_mode': 'execution', 'agent_view': 'hybrid',
            'update_every_steps': 1, 'diagnostic_progress_threshold': .3,
            'model': {'max_json_retries': 1},
            'sentinel': {'enabled': True, 'consistency_enabled': True,
                         'progress_enabled': True, 'local_audit_every_steps': 1,
                         'global_audit_every_steps': 32,
                         'recent_transition_count': 4},
            'trapping': {'enabled': True, 'window_size': 8,
                         'recurrence_epsilon': .15, 'max_cycle_length': 4,
                         'health_threshold': .25, 'cycle_threshold': .75},
            'recovery': {'enabled': True, 'recent_low_progress_count': 4},
        },
    }


class PoSEpisode:
    """One completed GA decision/batch becomes one PoS transition."""

    def __init__(self, *, case_id, config, logger, belief_call, consistency_call,
                 progress_call):
        self.case_id = case_id
        self.config = deepcopy(config)
        self.logger = logger
        self.manager = BeliefManager(self.config, belief_call, logger,
                                     call_sentinel=consistency_call,
                                     call_progress=progress_call)
        self.started = False
        self.ended = False
        self.success_known = False
        self.step = 0
        self.completed_decision_batches = 0
        self.state = None
        self.lifecycle = []
        self.terminal_status = None

    def reset(self, *, task, observation, actions):
        if self.started:
            raise RuntimeError('PoS episode already started')
        self.state = dict(case_id=self.case_id, task=task, observation=observation,
                          actions=actions, done=False, success=False, score=0.0)
        self.manager.reset(deepcopy(self.state))
        self.started = True
        self.lifecycle.append({'kind': 'reset', 'success_known': False})
        return self.get_context()

    def update(self, *, thought, action_batch, observation, done=False):
        if not self.started or self.ended:
            raise RuntimeError('PoS episode is not active')
        if not action_batch:
            raise ValueError('empty batch is not a PoS action transition')
        self.state = {**self.state, 'observation': observation, 'done': bool(done),
                      'success': False, 'score': 0.0}
        transition = {'thought': thought, 'action': deepcopy(action_batch),
                      'observation': observation}
        self.manager.update(transition, deepcopy(self.state), self.step)
        self.lifecycle.append({'kind': 'update', 'step': self.step,
                               'batch_size': len(action_batch),
                               'success_known': False, 'done': bool(done)})
        self.step += 1
        if done:
            self.ended = True
        return self.get_context()

    def decision_completed(self, *, turn, action_count):
        """Count a GA decision independently of PoS scored transitions."""
        if not self.started or self.ended:
            raise RuntimeError('PoS episode is not active')
        self.completed_decision_batches += 1
        self.lifecycle.append({'kind': 'decision_completed', 'turn': turn,
                               'action_count': action_count})
        return {'completed_decision_batches': self.completed_decision_batches}

    def finish(self, *, reason, observation=None):
        if not self.started:
            return {'status': 'never_started', 'reason': reason}
        if observation is not None:
            self.state['observation'] = observation
        self.state['done'] = True
        self.ended = True
        self.manager.close()
        self.terminal_status = ('completed' if reason == 'CURRENT_TASK_DONE' else
                                'partial' if reason in {'MAX_TURNS_EXCEEDED', 'EXITED',
                                                       'provider_cancelled', 'interrupted'} else
                                'failed')
        self.lifecycle.append({'kind': 'finish', 'reason': reason,
                               'success_known': False})
        return self.get_result()

    def get_context(self):
        if not self.started:
            raise RuntimeError('PoS episode not initialized')
        return self.manager.get_context()

    def decision_view(self, *, current_observation, actions, runtime_constraints=''):
        """Render the released hybrid semantics with GA's native action envelope."""
        if not self.started or self.ended:
            raise RuntimeError('PoS decision unavailable')
        state = {**self.state, 'observation': current_observation,
                 'actions': deepcopy(actions)}
        context = self.get_context()
        gap = context.get('frontier_gap')
        structured = {'goal': context.get('goal'),
                      'world': _frontier_relevant_world(context.get('world', {}), gap)}
        recovery = context.get('recovery')
        system = ('Use GA native mounted tools to pursue the task. Multiple native tool '
                  'calls in one decision are allowed. Do not emit benchmark JSON '
                  'thought/action. GA retains its original completion '
                  'and tool protocols; PoS context is decision support, not an approval gate.')
        sections = [
            'Current observation:\n' + str(state['observation']),
            'Belief Text:\n' + str(context['belief_text']),
            'Goal and Active-Gap structured subgraph:\n' +
                json.dumps(structured, ensure_ascii=False),
            'Active Gap:\n' + json.dumps(gap, ensure_ascii=False),
            FRONTIER_ACTION_SELECTION_CONTRACT,
        ]
        if recovery is not None:
            sections.append('Recovery constraint C_t:\n' + json.dumps(recovery, ensure_ascii=False))
        if runtime_constraints:
            sections.append('Current runtime constraints and instructions:\n' + runtime_constraints)
        sections.append('Use the mounted GA native tool schema; the provider request '
                        'contains the single authoritative tool definition set.')
        user = '\n\n'.join(sections)
        return {'system': system, 'user': user,
                'context': context, 'adaptation': 'native_tool_envelope_only'}

    def get_result(self):
        result = self.manager.get_result() if self.started else {}
        return {'status': self.terminal_status or 'partial',
                'host_terminal_reason': (self.lifecycle[-1].get('reason')
                    if self.lifecycle and self.lifecycle[-1]['kind'] == 'finish' else None),
                'core_last_transition_done': (self.manager.health_transitions[-1].done
                    if getattr(self.manager, 'health_transitions', []) else None),
                'success_known': self.success_known, 'task_success': None,
                'completed_decision_batches': self.completed_decision_batches,
                'scored_transitions': sum(item.progress in (0, 1) for item in
                    getattr(self.manager, 'health_transitions', [])),
                'lifecycle': deepcopy(self.lifecycle), **result}
