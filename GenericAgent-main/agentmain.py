import os, sys, threading, queue, time, json, re, random, locale, glob
os.environ.setdefault('GA_LANG', 'zh' if any(k in (locale.getlocale()[0] or '').lower() for k in ('zh', 'chinese')) else 'en')
if sys.stdout is None: sys.stdout = open(os.devnull, "w")
elif hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(errors='replace')
if sys.stderr is None: sys.stderr = open(os.devnull, "w")
elif hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(errors='replace')
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from llmcore import reload_mykeys, ToolClient, MixinSession, NativeToolClient, NativeClaudeSession, NativeOAISession, resolve_client
from agent_loop import agent_runner_loop
try:
    from plugins.hooks import discover_and_load; discover_and_load()
except Exception: pass
from ga import GenericAgentHandler, smart_format, get_global_memory, format_error, consume_file
from research_runtime import JsonlEventSink, new_id as research_id, telemetry_enabled, wrap_generator
from experiment_conditions import condition_from_environment
from workspace_runtime import prepare_task_query, resolve_workspace_dir, workspace_contract
from obligation_ledger import ObligationLedger
from public_checker import checker_from_card
from evidence_state import CARD_SCHEMA, EvidenceCarryingState
from completion_contract import CompletionContract
from evidence_completion_kernel import EvidenceCompletionKernel
from online_evidence_gate import OnlineEvidenceCompletionGate
from completion_checkpoint import FirstCompletionCheckpoint, checkpoint_identity_from_environment
from manual_completion_boundary import ManualCompletionBoundary
from task_interruption import ResumableInterruption
from candidate_online_gate import CandidateOnlineEvidenceGate
from recovery_presentation_gate import RecoveryPresentationGate
from priority_residual_gate import POLICIES as PRIORITY_RESIDUAL_POLICIES, PriorityResidualRecoveryGate
from assumption_audit_gate import AssumptionAuditCompletionGate

script_dir = os.path.dirname(os.path.abspath(__file__))
BANNED_TOOLS = (['ask_user', 'start_long_term_update'] if '--no-user-tools' in sys.argv else [])
def load_tool_schema(suffix=''):
    global TOOLS_SCHEMA
    TS = open(os.path.join(script_dir, f'assets/tools_schema{suffix}.json'), 'r', encoding='utf-8').read()
    TOOLS_SCHEMA = json.loads(TS if os.name == 'nt' else TS.replace('powershell', 'bash'))
    TOOLS_SCHEMA = [t for t in TOOLS_SCHEMA if t.get('function', {}).get('name') not in BANNED_TOOLS]
load_tool_schema()

lang_suffix = '_en' if os.environ.get('GA_LANG', '') == 'en' else ''
mem_dir = os.path.join(script_dir, 'memory')
if not os.path.exists(mem_dir): os.makedirs(mem_dir)
mem_txt = os.path.join(mem_dir, 'global_mem.txt')
if not os.path.exists(mem_txt): open(mem_txt, 'w', encoding='utf-8').write('# [Global Memory - L2]\n')
mem_insight = os.path.join(mem_dir, 'global_mem_insight.txt')
if not os.path.exists(mem_insight):
    t = os.path.join(script_dir, f'assets/global_mem_insight_template{lang_suffix}.txt')
    open(mem_insight, 'w', encoding='utf-8').write(open(t, encoding='utf-8').read() if os.path.exists(t) else '')
cdp_cfg = os.path.join(script_dir, 'assets/tmwd_cdp_bridge/config.js')
if not os.path.exists(cdp_cfg):
    try:
        os.makedirs(os.path.dirname(cdp_cfg), exist_ok=True)
        open(cdp_cfg, 'w', encoding='utf-8').write(f"const TID = '__ljq_{hex(random.randint(0, 99999999))[2:8]}';")
    except Exception as e: print(f'[WARN] CDP config init failed: {e} — advanced web features (tmwebdriver) will be unavailable.')

def get_system_prompt():
    with open(os.path.join(script_dir, f'assets/sys_prompt{lang_suffix}.txt'), 'r', encoding='utf-8') as f: prompt = f.read()
    prompt += f"\nToday: {time.strftime('%Y-%m-%d %a')}\n"
    prompt += get_global_memory()
    return prompt


def restore_history_file(agent, histfile):
    """Load either legacy history arrays or an R1 checkpoint session object."""
    saved = json.loads(open(histfile, encoding='utf-8').read())
    if isinstance(saved, dict) and 'history' in saved:
        agent.llmclient.backend.history = saved['history']
        agent.llmclient.last_tools = saved.get('last_tools', '')
        return saved
    if not isinstance(saved, list):
        raise ValueError('History file must contain a message list or checkpoint session')
    agent.llmclient.backend.history = saved
    return {'history': saved}


def checkpoint_turn_offset(checkpoint_dir):
    """Return the last global turn captured by an R1 completion checkpoint."""
    packet = json.loads(open(os.path.join(checkpoint_dir, 'packet.json'), encoding='utf-8').read())
    if packet.get('boundary') != 'pre_completion_decision':
        raise ValueError('Completion branch requires a pre_completion_decision checkpoint')
    turn = packet.get('identity', {}).get('internal_turn')
    if not isinstance(turn, int) or turn < 0:
        raise ValueError('Completion checkpoint has no valid global internal_turn')
    return turn

# SDK:
# agent = GenericAgent(); threading.Thread(target=agent.run, daemon=True).start()
# output1_queue = agent.put_task(prompt1)
# output2_queue = agent.put_task(prompt2)
class GenericAgent:
    def __init__(self):
        os.makedirs(os.path.join(script_dir, 'temp'), exist_ok=True)
        self.lock = threading.Lock()
        self.task_dir = None
        self.workspace_dir = None
        self.research_turn_offset = 0
        self.history = []; self.handler = None; 
        self.task_queue = queue.Queue() 
        self.is_running = False; self.stop_sig = False; self.llm_no = 0;  
        self.resumable_interruption = ResumableInterruption()
        self.inc_out = False; self.verbose = True
        self.peer_hint = True
        self.force_non_stream = False
        logid = f'{(time.time_ns() + random.randrange(1_000_000)) % 1_000_000:06d}'
        self.log_path = os.path.join(script_dir, f'temp/model_responses/model_responses_{logid}.txt')
        self.load_llm_sessions()
        self.extra_sys_prompts = []
        self.intervene = self.extrakeyinfo = None
        ledger_card = os.environ.get('GA_OBLIGATION_LEDGER_CARD_PATH')
        if ledger_card:
            ledger_data = json.loads(open(ledger_card, encoding='utf-8').read())
            checker = checker_from_card(ledger_data, lambda: self.workspace_dir or self.task_dir)
            self.obligation_ledger = ObligationLedger.from_card(ledger_data, checker_runner=checker)
        else:
            self.obligation_ledger = None
        evidence_state_path = os.environ.get('GA_EVIDENCE_STATE_PATH')
        completion_contract_path = os.environ.get('GA_COMPLETION_CONTRACT_PATH')
        public_task_path = os.environ.get('GA_PUBLIC_TASK_PATH')
        self.evidence_completion_kernel = None
        if any((evidence_state_path, completion_contract_path, public_task_path)):
            if not all((evidence_state_path, completion_contract_path, public_task_path)):
                raise ValueError('Stage 6D requires state, contract, and public task paths together')
            state_value = json.loads(open(evidence_state_path, encoding='utf-8').read())
            state_body = state_value.get('state', state_value)
            state = (
                EvidenceCarryingState.from_card(state_body)
                if state_body.get('schema_version') == CARD_SCHEMA
                else EvidenceCarryingState.from_snapshot(state_body)
            )
            contract_value = json.loads(open(completion_contract_path, encoding='utf-8').read())
            contract_body = contract_value.get('contract', contract_value)
            task_text = open(public_task_path, encoding='utf-8').read()
            contract = CompletionContract.from_dict(contract_body, state, task_text)
            frontend_config = os.environ.get('GA_EVIDENCE_FRONTEND_CONFIG')
            audit_card_path = os.environ.get('GA_REPRESENTATION_AUDIT_CARD_PATH')
            evidence_gate_mode = os.environ.get('GA_EVIDENCE_GATE_MODE', '')
            shadow_only = evidence_gate_mode == 'lineage_shadow'
            recovery_style = 'hierarchical' if evidence_gate_mode == 'hierarchical_active' else 'flat'
            self.evidence_completion_kernel = (
                AssumptionAuditCompletionGate(
                    state, contract, frontend_config,
                    disposition_card=json.loads(open(audit_card_path, encoding='utf-8').read()),
                    public_task_text=task_text,
                    audit_config=os.environ.get('GA_REPRESENTATION_AUDIT_CONFIG'),
                    shadow_only=shadow_only, recovery_style=recovery_style,
                )
                if frontend_config and audit_card_path else OnlineEvidenceCompletionGate(
                    state, contract, frontend_config, shadow_only=shadow_only,
                    recovery_style=recovery_style,
                )
                if frontend_config else EvidenceCompletionKernel(state, contract)
            )
            branch_policy = os.environ.get('GA_COMPLETION_BRANCH_POLICY')
            branch_checkpoint = os.environ.get('GA_COMPLETION_BRANCH_CHECKPOINT')
            branch_bundle = os.environ.get('GA_COMPLETION_BRANCH_BUNDLE')
            if branch_policy or branch_checkpoint:
                if not all((branch_policy, branch_checkpoint, frontend_config)):
                    raise ValueError('Completion branch requires policy, checkpoint, and frontend config')
                self.research_turn_offset = checkpoint_turn_offset(branch_checkpoint)
                method_path = os.path.join(branch_checkpoint, 'state', 'method_state.json')
                method_value = json.loads(open(method_path, encoding='utf-8').read())
                gate_snapshot = method_value['completion_gate']
                branch_state = EvidenceCarryingState.from_snapshot(gate_snapshot['evidence_state'])
                if branch_policy in PRIORITY_RESIDUAL_POLICIES:
                    if not branch_bundle:
                        raise ValueError('Priority residual branch requires a branch bundle')
                    atoms_path = os.path.join(branch_bundle, 'atomic_discrepancies.json')
                    atoms_value = json.loads(open(atoms_path, encoding='utf-8').read())
                    candidate_gate = PriorityResidualRecoveryGate(
                        atoms_value['atoms'], policy_id=branch_policy,
                        max_recovery_episodes=int(atoms_value.get('max_recovery_episodes', 2)),
                    )
                else:
                    candidate_gate = RecoveryPresentationGate(
                        branch_state, contract, frontend_config,
                        presentation_id=branch_policy,
                    ) if branch_policy in {"I0", "I1", "I2"} else CandidateOnlineEvidenceGate(
                        branch_state, contract, frontend_config, policy_id=branch_policy,
                    )
                    candidate_gate.restore_snapshot(gate_snapshot)
                if branch_bundle:
                    branch_state_path = os.path.join(branch_bundle, 'branch_gate_state.json')
                    candidate_gate.restore_snapshot(json.loads(
                        open(branch_state_path, encoding='utf-8').read()
                    ))
                self.evidence_completion_kernel = candidate_gate
        self.completion_proposal_checkpoint_callback = None
        self.completion_decision_callback = None
        self.monitor_runtime = None
        completion_checkpoint_root = os.environ.get('GA_COMPLETION_CHECKPOINT_ROOT')
        if completion_checkpoint_root:
            def method_snapshot():
                gate = self.evidence_completion_kernel
                return {
                    'completion_gate': (
                        gate.snapshot() if hasattr(gate, 'snapshot') else {
                            'evidence_state': getattr(gate, 'state').snapshot()
                            if getattr(gate, 'state', None) is not None else None,
                        }
                    ),
                    'gate_mode': os.environ.get('GA_EVIDENCE_GATE_MODE', ''),
                }
            self.completion_proposal_checkpoint_callback = FirstCompletionCheckpoint(
                checkpoint_root=completion_checkpoint_root,
                workspace_getter=lambda: self.workspace_dir or self.task_dir,
                client=self.llmclient,
                identity=checkpoint_identity_from_environment(),
                method_getter=method_snapshot,
            )
        manual_completion_root = os.environ.get('GA_MANUAL_COMPLETION_DIR')
        if manual_completion_root:
            if os.environ.get('GA_MONITOR_ENABLED') == '1':
                raise ValueError('Choose manual supervision or automatic Monitor, not both')
            self.completion_decision_callback = ManualCompletionBoundary(
                manual_completion_root,
                timeout_seconds=float(os.environ.get('GA_MANUAL_COMPLETION_TIMEOUT_SECONDS', '300')),
            )
        self.research_checkpoint_callback = None

    def load_llm_sessions(self):
        mykeys, changed = reload_mykeys()
        if not changed and hasattr(self, 'llmclients'): return
        try: oldhistory = self.llmclient.backend.history
        except: oldhistory = None
        requested_config = os.environ.get('GA_LLM_CONFIG_NAME')
        if requested_config:
            selected = resolve_client(requested_config)
            if selected is None: raise ValueError(f'Unsupported GA_LLM_CONFIG_NAME: {requested_config}')
            self.llmclients = [selected]
            self.llmclient = selected
            self.llm_no = 0
            if oldhistory: self.llmclient.backend.history = oldhistory
            return
        llm_sessions = []
        for k, cfg in mykeys.items():
            try:
                if 'mixin' in k: llm_sessions += [{'mixin_cfg': cfg}]
                elif c := resolve_client(k): llm_sessions += [c]
            except: pass
        for i, s in enumerate(llm_sessions):
            if isinstance(s, dict) and 'mixin_cfg' in s:
                try:
                    mixin = MixinSession(llm_sessions, s['mixin_cfg'])
                    if isinstance(mixin._sessions[0], (NativeClaudeSession, NativeOAISession)): llm_sessions[i] = NativeToolClient(mixin)
                    else: llm_sessions[i] = ToolClient(mixin)
                except Exception as e: print(f'\n\n\n[ERROR] Failed to init MixinSession with cfg {s["mixin_cfg"]}: {e}!!!\n\n')
        self.llmclients = llm_sessions
        self.llmclient = self.llmclients[self.llm_no%len(self.llmclients)]
        if oldhistory: self.llmclient.backend.history = oldhistory
    
    def next_llm(self, n=-1):
        self.load_llm_sessions()
        self.llm_no = ((self.llm_no + 1) if n < 0 else n) % len(self.llmclients)
        lastc = self.llmclient
        self.llmclient = self.llmclients[self.llm_no]
        try: self.llmclient.backend.history = lastc.backend.history
        except: raise Exception('[ERROR] BAD Mixin config: Check your mykey.py')
        self.llmclient.last_tools = ''
        name = self.get_llm_name(model=True)
        if 'glm' in name or 'minimax' in name or 'kimi' in name: load_tool_schema('_cn')
        else: load_tool_schema()
    def list_llms(self): 
        self.load_llm_sessions()
        return [(i, self.get_llm_name(b), i == self.llm_no) for i, b in enumerate(self.llmclients)]
    def get_llm_name(self, b=None, model=False):
        b = self.llmclient if b is None else b
        if isinstance(b, dict): return 'BADCONFIG_MIXIN'
        if model: return b.backend.model.lower()
        return f"{type(b.backend).__name__}/{b.backend.name}"

    def abort(self):
        if not self.is_running: return
        print('Abort current task...')
        self.stop_sig = True
        if self.handler is not None: self.handler.code_stop_signal.append(1)
        cancel = getattr(getattr(self.llmclient, 'backend', None), 'cancel_active_response', None)
        if cancel is not None: cancel()

    def request_monitor_interruption(self, message):
        """Cancel the current action and resume this task with a monitor message."""
        request = self.resumable_interruption.request(message, source="monitor")
        if self.handler is not None: self.handler.code_stop_signal.append(1)
        cancel = getattr(getattr(self.llmclient, 'backend', None), 'cancel_active_response', None)
        if cancel is not None: cancel()
        return request

    def consume_resumable_interruption(self):
        return self.resumable_interruption.consume()
            
    def put_task(self, query, source="user", images=None):
        display_queue = queue.Queue()
        self.task_queue.put({"query": query, "source": source, "images": images or [], "output": display_queue})
        return display_queue

    # i know it is dangerous, but raw_query is dangerous enough it doesn't enlarge
    def _handle_slash_cmd(self, raw_query, display_queue):
        if not raw_query.startswith('/'): return raw_query
        if _sm := re.match(r'/session\.(\w+)=(.*)', raw_query.strip()):
            k, v = _sm.group(1), _sm.group(2)
            vfile = os.path.join(script_dir, 'temp', v)
            if os.path.isfile(vfile): v = open(vfile, encoding='utf-8').read().strip()
            try: v = json.loads(v)  # cover number parsing
            except (json.JSONDecodeError, ValueError): pass
            setattr(self.llmclient.backend, k, v)
            display_queue.put({'done': smart_format(f"✅ session.{k} = {repr(v)}", max_str_len=500), 'source': 'system'})
            return None
        if raw_query.strip() == '/resume':
            return r'帮我看看最近有哪些会话可以恢复。读model_responses/目录，按修改时间取最近10个文件，从每个文件里找最后一个<history>...</history>块，用一句话总结每个会话在聊什么，列表给我选。注意读文件后要把字面的\n替换成真换行才能正确匹配。'
        return raw_query

    def run(self):
        while True:
            task = self.task_queue.get()
            if isinstance(task, str): break
            raw_query, source, display_queue = task["query"], task["source"], task["output"]
            raw_query = self._handle_slash_cmd(raw_query, display_queue)
            if raw_query is None:
                self.task_queue.task_done(); continue
            self.is_running = True
            handler_cwd = self.workspace_dir or resolve_workspace_dir(self.task_dir)
            raw_query = prepare_task_query(
                raw_query, self.task_dir,
                inline_long=os.environ.get('GA_INLINE_LONG_PROMPT') == '1',
            )
            if os.environ.get('GA_M0_MONITOR_ENABLED') == '1':
                raise RuntimeError(
                    'GA_M0_MONITOR_ENABLED is a retired historical runtime. '
                    'Use the clean GA_MONITOR_ENABLED path.'
                )
            if os.environ.get('GA_MONITOR_ENABLED') == '1' and self.monitor_runtime is None:
                from ga_monitor_adapter import GenericAgentMonitorAdapter
                monitor_config_name = os.environ.get(
                    'GA_MONITOR_CONFIG', 'native_oai_cc_vibe_gpt56_sol_high'
                )
                monitor_model_config = reload_mykeys()[0].get(monitor_config_name)
                if not monitor_model_config:
                    raise ValueError(f'Unknown GA_MONITOR_CONFIG: {monitor_config_name}')
                artifact_dir = os.environ.get('GA_MONITOR_ARTIFACT_DIR') or os.path.join(
                    script_dir, 'temp', 'clean_monitor',
                    os.environ.get('GA_BENCH_RUN_ID') or research_id('monitor_run')
                )
                self.monitor_runtime = GenericAgentMonitorAdapter(
                    public_task=raw_query,
                    task_workspace=handler_cwd,
                    artifact_dir=artifact_dir,
                    config_name=monitor_config_name,
                    model_config=monitor_model_config,
                    interrupt_callback=self.request_monitor_interruption,
                    max_review_turns=int(os.environ.get('GA_MONITOR_MAX_REVIEW_TURNS', '20')),
                    completion_timeout=float(os.environ.get('GA_MONITOR_COMPLETION_TIMEOUT_SECONDS', '300')),
                )
                self.research_checkpoint_callback = None
                self.completion_decision_callback = self.monitor_runtime.review_completion
            rquery = smart_format(raw_query.replace('\n', ' '), max_str_len=200)
            self.history.append(f"[USER]: {rquery}")
            if not hasattr(self, 'research_condition'):
                self.research_condition = condition_from_environment(raw_query)
            sys_prompt = get_system_prompt() + '\n'.join(self.extra_sys_prompts) + getattr(self.llmclient.backend, 'extra_sys_prompt', '')
            sys_prompt += workspace_contract(handler_cwd)
            if self.peer_hint: sys_prompt += f"\n[Peer] 用户提及其他会话/后台任务状态时: temp/model_responses/ (只找近期修改的文件尾部)\n"
            handler = GenericAgentHandler(self, self.history, handler_cwd)
            if getattr(self, 'no_print', False): handler.print = lambda *a, **k: None
            if self.handler and 'key_info' in self.handler.working: 
                ki = re.sub(r'\n\[SYSTEM\] 此为.*?工作记忆[。\n]*', '', self.handler.working['key_info'])  # 去旧
                handler.working['key_info'] = ki
                handler.working['passed_sessions'] = ps = self.handler.working.get('passed_sessions', 0) + 1
                if ps > 0: handler.working['key_info'] += f'\n[SYSTEM] 此为 {ps} 个对话前设置的key_info，若已在新任务，先更新或清除工作记忆。\n'
            self.handler = handler  # although new handler, the **full** history is in llmclient, so it is full history!
            self.llmclient.log_path = self.log_path
            if self.force_non_stream:
                self.llmclient.backend.stream = False
                self.llmclient.backend.read_timeout = max(self.llmclient.backend.read_timeout, 1200)
            max_turns = int(os.environ.get('GA_MAX_TURNS', '180'))
            gen = agent_runner_loop(self.llmclient, sys_prompt, raw_query, handler, TOOLS_SCHEMA,
                                    max_turns=max_turns, verbose=self.verbose, yield_info=True,
                                    turn_offset=self.research_turn_offset)
            event_path = getattr(self, 'research_event_path', None) or os.environ.get('GA_RESEARCH_EVENT_PATH')
            if event_path or telemetry_enabled():
                identity = dict(getattr(self, 'research_identity', {}) or {})
                identity.setdefault('experiment_id', os.environ.get('GA_EXPERIMENT_ID') or 'interactive')
                identity.setdefault('condition_id', os.environ.get('GA_CONDITION_ID') or 'original')
                identity.setdefault('run_id', os.environ.get('GA_BENCH_RUN_ID') or research_id('run'))
                identity.setdefault('branch_id', 'original')
                identity.setdefault('task_id', os.environ.get('GA_BENCH_TASK_ID') or
                                    (os.path.basename(self.task_dir) if self.task_dir else 'interactive'))
                gen = wrap_generator(gen, identity, JsonlEventSink(event_path) if event_path else None)
            manual_inbox = None
            try:
                full_resp = ""; last_pos = 0; curr_turn = 0; turn_resps = []
                manual_root = os.environ.get('GA_MANUAL_COMPLETION_DIR')
                if manual_root:
                    from manual_completion_boundary import ManualInterventionInbox
                    manual_inbox = ManualInterventionInbox(
                        os.path.join(manual_root, 'interventions'),
                        self.request_monitor_interruption,
                    ).start()
                for chunk in gen:
                    if consume_file(self.task_dir, '_stop'): self.abort() 
                    if self.stop_sig: break
                    if isinstance(chunk, dict) and 'turn' in chunk: 
                        curr_turn = chunk['turn']; turn_resps.append(''); continue
                    full_resp += chunk;  turn_resps[-1] += chunk
                    if len(full_resp) - last_pos > 30 or 'LLM Running' in chunk:
                        display_queue.put({'next': full_resp[last_pos:] if self.inc_out else full_resp, 
                                           'source': source, 'turn': curr_turn, 'outputs': turn_resps[-2:]})
                        last_pos = len(full_resp)
                if self.inc_out and last_pos < len(full_resp):
                    display_queue.put({'next': full_resp[last_pos:], 'source': source,
                                    'turn': curr_turn, 'outputs': turn_resps[-2:]})
                display_queue.put({'done': full_resp, 'source': source, 'turn': curr_turn, 'outputs': turn_resps.copy()})
                self.history = handler.history_info
            except Exception as e:
                print(f"Backend Error: {format_error(e)}")
                display_queue.put({'done': full_resp + f'\n```\n{format_error(e)}\n```', 'source': source, 'turn': curr_turn, 'outputs': turn_resps.copy()})
            finally:
                if manual_inbox is not None:
                    manual_inbox.close()
                if self.stop_sig: print('User aborted the task.')
                if self.monitor_runtime is not None:
                    self.monitor_runtime.close()
                    self.monitor_runtime = None
                self.is_running = self.stop_sig = False
                self.task_queue.task_done()
                if self.handler is not None: self.handler.code_stop_signal.append(1)

GeneraticAgent = GenericAgent

if __name__ == '__main__':
    import argparse
    from datetime import datetime
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', metavar='IODIR', help='一次性任务模式，先看subagent.md')
    parser.add_argument('--func', metavar='PROMPT_FILE', help='纯函数模式：读prompt文件→结果写prompt.out.txt→退出')
    parser.add_argument('--reflect', metavar='SCRIPT', help='反射模式：加载监控脚本，check()触发时发任务')
    parser.add_argument('--input', help='prompt')
    parser.add_argument('--history', help='history json file')
    parser.add_argument('--llm_no', type=int, default=0)
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--nobg', action='store_true')
    parser.add_argument('--nolog', action='store_true')
    parser.add_argument('--no-user-tools', action='store_true')
    args, _unknown = parser.parse_known_args()
    _extra_args = dict(zip([k.lstrip('-') for k in _unknown[::2]], _unknown[1::2])) if _unknown else {}

    if (args.func or args.task) and not args.nobg:
        import subprocess, platform
        cmd = [sys.executable, os.path.abspath(__file__)] + [a for a in sys.argv[1:]] + ['--nobg']
        if args.task:
            d = os.path.join(script_dir, f'temp/{args.task}'); os.makedirs(d, exist_ok=True)
            out = open(os.path.join(d, 'stdout.log'), 'w', encoding='utf-8')
            err = open(os.path.join(d, 'stderr.log'), 'w', encoding='utf-8')
        else: out, err = subprocess.DEVNULL, subprocess.DEVNULL
        p = subprocess.Popen(cmd, cwd=script_dir,
            creationflags=0x08000000 if platform.system() == 'Windows' else 0,
            stdout=out, stderr=err)
        print('PID:', p.pid); sys.exit(0)

    agent = GenericAgent()
    if args.nolog: agent.log_path = False
    agent.next_llm(args.llm_no)
    agent.verbose = args.verbose
    threading.Thread(target=agent.run, daemon=True).start()

    histfile = args.history
    if args.task:
        agent.task_dir = d = os.path.join(script_dir, f'temp/{args.task}'); nround = ''
        agent.workspace_dir = resolve_workspace_dir(agent.task_dir)
        infile = os.path.join(d, 'input.txt'); outfile = f'{d}/output{nround}.txt'
        if args.input:
            os.makedirs(d, exist_ok=True)
            [os.remove(f) for f in glob.glob(os.path.join(d, 'output*.txt'))]
            with open(infile, 'w', encoding='utf-8') as f: f.write(args.input)
        histfile = histfile or os.path.join(d, '_history.json')
    elif args.func:
        infile = args.func; outfile = os.path.splitext(args.func)[0] + '.out.txt'
    
    if histfile and os.path.isfile(histfile): restore_history_file(agent, histfile)

    if args.func or args.task:
        agent.peer_hint = False
        with open(infile, encoding='utf-8') as f: raw = f.read()
        while True:
            dq = agent.put_task(raw, source='func' if args.func else 'task')
            while 'done' not in (item := dq.get(timeout=2200)): 
                if 'next' in item: 
                    with open(outfile, 'w', encoding='utf-8') as f: f.write(item.get('next', ''))
            with open(outfile, 'w', encoding='utf-8') as f: f.write(item['done'] + '\n\n[ROUND END]\n')
            if not args.task: break
            consume_file(d, '_stop')  # 已经成功停下来了，避免打断下次reply
            for _ in range(300):  # 等reply.txt，10分钟超时
                time.sleep(2)
                if (raw := consume_file(d, 'reply.txt')): break
            else: break
            nround = nround + 1 if isinstance(nround, int) else 1
            outfile = f'{d}/output{nround}.txt'
    elif args.reflect:
        agent.peer_hint = False
        import importlib.util
        spec = importlib.util.spec_from_file_location('reflect_script', args.reflect)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        if hasattr(mod, 'init'): mod.init(_extra_args)
        _mt = os.path.getmtime(args.reflect)
        print(f'[Reflect] loaded {args.reflect}' + (f' args={_extra_args}' if _extra_args else ''))
        while True:
            if os.path.getmtime(args.reflect) != _mt:
                try:
                    spec.loader.exec_module(mod); _mt = os.path.getmtime(args.reflect)
                    if hasattr(mod, 'init'): mod.init(_extra_args)
                    print('[Reflect] reloaded')
                except Exception as e: print(f'[Reflect] reload error: {e}')
            try: task = mod.check()
            except Exception as e: 
                print(f'[Reflect] check() error: {e}'); task = None
            if task and task == '/exit': break
            if task:
                print(f'[Reflect] triggered: {task[:80]}')
                dq = agent.put_task(task, source='reflect')
                try:
                    while 'done' not in (item := dq.get(timeout=2200)): pass
                    result = item['done']
                    print(result)
                except Exception as e:
                    if getattr(mod, 'ONCE', False): raise
                    print(f'[Reflect] drain error: {e}'); result = f'[ERROR] {e}'
                log_dir = os.path.join(script_dir, 'temp/reflect_logs'); os.makedirs(log_dir, exist_ok=True)
                script_name = os.path.splitext(os.path.basename(args.reflect))[0]
                open(os.path.join(log_dir, f'{script_name}_{datetime.now():%Y-%m-%d}.log'), 'a', encoding='utf-8').write(f'[{datetime.now():%m-%d %H:%M}]\n{result}\n\n')
                if (on_done := getattr(mod, 'on_done', None)):
                    try: on_done(result)
                    except Exception as e: print(f'[Reflect] on_done error: {e}')
                if getattr(mod, 'ONCE', False): print('[Reflect] ONCE=True, exiting.'); break
            time.sleep(getattr(mod, 'INTERVAL', 5))
    else:
        try: import readline
        except Exception: pass
        agent.inc_out = True
        if sys.stdout.isatty():
            try: model = agent.get_llm_name(model=True) or '?'
            except Exception: model = '?'
            try:
                sys.stdout.write(f'\x1b[92m✦\x1b[0m \x1b[1mGenericAgent\x1b[0m '
                                 f'\x1b[90m· cli · model:\x1b[0m {model}\n')
                sys.stdout.flush()
            except Exception: pass
        while True:
            q = input('> ').strip()
            if not q: continue
            try:
                dq = agent.put_task(q, source='user')
                while True:
                    item = dq.get()
                    if 'next' in item: print(item['next'], end='', flush=True)
                    if 'done' in item: print(); break
            except KeyboardInterrupt:
                agent.abort(); print('\n[Interrupted]')
