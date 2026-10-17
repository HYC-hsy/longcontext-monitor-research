"""Thin GA lifecycle adapter around the unmodified released PoS BeliefManager.

This module is imported only by an isolated worker with ``vendor`` on sys.path.
The caller owns Task actions and termination; no PMA object is instantiated.
"""
from __future__ import annotations

from copy import deepcopy
import json

from belief.manager import BeliefManager
from prompts.react_prompt import build_belief_prompt


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
        """Use released hybrid builder; adapt only its JSON action envelope."""
        if not self.started or self.ended:
            raise RuntimeError('PoS decision unavailable')
        state = {**self.state, 'observation': current_observation,
                 'actions': deepcopy(actions)}
        original = build_belief_prompt(state, self.get_context(), self.config)
        system = (original[0]['content'] + '\n\nGA native-action envelope: use the mounted '
                  'tool schema and emit native tool calls; the JSON thought/action format '
                  'above is replaced only at the action-transport boundary. Do not treat '
                  'a reminder, health score, or empty gap as permission to terminate.')
        user = (original[1]['content'] + '\n\nFull mounted native tool schemas:\n' +
                json.dumps(actions, ensure_ascii=False) +
                ('\n\nCurrent runtime constraints and instructions:\n' +
                 runtime_constraints if runtime_constraints else ''))
        return {'system': system, 'user': user,
                'context': self.get_context(), 'upstream_messages': original}

    def get_result(self):
        result = self.manager.get_result() if self.started else {}
        return {'status': self.terminal_status or 'partial',
                'success_known': self.success_known, 'task_success': None,
                'scored_decision_batches': self.step,
                'lifecycle': deepcopy(self.lifecycle), **result}
