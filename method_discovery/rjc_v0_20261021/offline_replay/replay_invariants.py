"""Zero-model offline replay of two candidate invariants on archived GA/PoS/PMA runs.

Invariant R1 (failure receipt closure): a requirement-bound failure receipt may be
closed only by citing a later tool receipt, never by model interpretation alone.
Invariant R2 (completion gap handling): at the Task completion proposal, every gap
still open in the last accepted PoS state must have been addressed.

This script only reads archived public events and reports where each invariant
would fire. It does not judge semantic correctness and uses no model calls.
"""
import glob
import json
import os
import re
import sys

STOP = set("""the and with for from that this into make made over use used using
instead sources network available compile compiled install installed snapshot
pre-vendored vendored fetching should must when then than them have has been
will your also only just file files directory""".split())
FAIL_PAT = re.compile(r'command not found|not found|No such file|Permission denied|'
                      r'cannot |failed|error:', re.I)
RESOLVED_PAT = re.compile(r'satisf|complete|resolved|red herring|expected behavior|'
                          r'not a failure|is fine|works|working|success|done', re.I)


def jl(path):
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if line:
            yield json.loads(line)


def _collect_results(obj, out):
    """Collect tool receipts from nested message content (full history or PoS view)."""
    if isinstance(obj, dict):
        if obj.get('type') == 'tool_result' and 'tool_use_id' in obj:
            raw = obj.get('content')
            parsed = {}
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = {'stdout': raw}
            out[obj['tool_use_id']] = parsed if isinstance(parsed, dict) else {'stdout': str(parsed)}
            return
        if 'tool_results' in obj and isinstance(obj['tool_results'], list):
            for tr in obj['tool_results']:
                if isinstance(tr, dict) and tr.get('tool_use_id'):
                    res = tr.get('result')
                    out[tr['tool_use_id']] = res if isinstance(res, dict) else {'stdout': str(res)}
            return
        if obj.get('type') == 'text' and isinstance(obj.get('text'), str) and \
                obj['text'].startswith('Current observation:'):
            try:
                _collect_results(json.loads(obj['text'].split('\n', 1)[1]), out)
            except Exception:
                pass
        for v in obj.values():
            _collect_results(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_results(v, out)


def load_task(run):
    files = sorted(glob.glob(os.path.join(run, 'task', '**', 'research_events*.jsonl'),
                             recursive=True))
    term = proposal = None
    task_text = None
    uses, results, order = {}, {}, []
    for f in files:
        for d in jl(f):
            t = d.get('event_type')
            if t == 'provider_request_ready':
                msgs = d['payload']['content']['messages']
                if task_text is None:
                    first = msgs[0]['content']
                    task_text = first[0]['text'] if isinstance(first, list) else str(first)
                _collect_results(msgs, results)
                for m in msgs:
                    for b in (m['content'] if isinstance(m['content'], list) else []):
                        if b.get('type') == 'tool_use' and b['id'] not in uses:
                            uses[b['id']] = b
                            order.append(b['id'])
            elif t == 'provider_response_content':
                for b in d['payload'].get('parsed_visible_blocks', []):
                    if b.get('type') == 'tool_use' and b['id'] not in uses:
                        uses[b['id']] = b
                        order.append(b['id'])
            elif t == 'termination':
                term = d
            elif t == 'completion_proposal':
                proposal = d
    receipts = []
    for tid in order:
        if tid not in results:
            continue
        u, p = uses[tid], results[tid]
        receipts.append({'turn': len(receipts) + 1, 'name': u.get('name'),
                         'script': json.dumps(u.get('input', {}), ensure_ascii=False),
                         'stdout': str(p.get('stdout', '')), 'stderr': str(p.get('stderr', '')),
                         'exit_code': p.get('exit_code'), 'status': p.get('status')})
    goal = re.sub(r'\s+', ' ', task_text or '')
    final_text = json.dumps(term['payload'], ensure_ascii=False) if term else ''
    return goal, receipts, final_text, proposal


def requirement_terms(task_text):
    terms = set(re.findall(r'/[\w./-]+', task_text))
    for w in re.findall(r'[A-Za-z][\w-]{3,}', task_text):
        lw = w.lower()
        if lw not in STOP:
            terms.add(w if w.isupper() else lw)
    return sorted(terms, key=len, reverse=True)


def mentions(text, term):
    if term.isupper():
        return re.search(r'\b' + re.escape(term) + r'\b', text) is not None
    return term.lower() in text.lower()


def failure_receipts(receipts, terms):
    out = []
    for r in receipts:
        text = r['stdout'] + '\n' + r['stderr']
        failed = (r['exit_code'] not in (0, None)) or FAIL_PAT.search(text)
        if not failed:
            continue
        lines = [ln for ln in text.splitlines() if FAIL_PAT.search(ln)]
        hits = [t for t in terms if any(mentions(ln, t) for ln in lines)]
        if not hits and r['exit_code'] not in (0, None):
            hits = [t for t in terms if mentions(r['script'], t)]
        if hits:
            out.append({'turn': r['turn'], 'exit_code': r['exit_code'],
                        'terms': hits, 'fail_lines': lines[:4]})
    return out


def later_receipts_for(receipts, term, after_turn):
    """Later receipts whose script mentions the term: candidates a closer could cite."""
    return [r['turn'] for r in receipts
            if r['turn'] > after_turn and mentions(r['script'] + '\n' + r['stdout'], term)]


def load_pos_states(run):
    states = []
    for f in sorted(glob.glob(os.path.join(run, 'pos', 'events.jsonl.part*.jsonl'))):
        for d in jl(f):
            if d.get('event') in ('belief_state_initialized', 'belief_state_updated'):
                b = d['belief_state']
                states.append({'step': d['step'], 'time': d['time'],
                               'achievement': [g['target'] for g in b.get('achievement_gaps', [])],
                               'epistemic': [g['target'] for g in b.get('epistemic_gaps', [])]})
    return states


def load_pma_ops(run):
    reqs = {}
    for f in glob.glob(os.path.join(run, 'spool', 'requests', '*.json')):
        d = json.load(open(f, encoding='utf-8'))
        step = re.search(r'## Step (\d+)', d.get('prompt', ''))
        reqs[d['event_id']] = {'seq': d.get('sequence'), 'role': d.get('role'),
                               'step': int(step.group(1)) if step else None}
    ops = []
    for f in glob.glob(os.path.join(run, 'spool', 'responses', '*.json')):
        d = json.load(open(f, encoding='utf-8'))
        meta = reqs.get(d['event_id'], {})
        res = d.get('result') or {}
        for tc in res.get('tool_calls') or []:
            ops.append({**meta, 'tool': tc.get('name'),
                        'content': json.dumps(tc.get('arguments'), ensure_ascii=False)})
        if meta.get('role') == 'pma_phase2':
            ops.append({**meta, 'tool': 'phase2_text', 'content': res.get('content', '')})
    return sorted(ops, key=lambda o: (o.get('seq') is None, o.get('seq') or 0))


def rule1(task_text, receipts, states, pma_ops):
    terms = requirement_terms(task_text)
    fails = failure_receipts(receipts, terms)
    findings = []
    for fr in fails:
        for term in fr['terms']:
            later = later_receipts_for(receipts, term, fr['turn'])
            for op in pma_ops:
                step = op.get('step')
                if step is None or step < fr['turn']:
                    continue
                if not (mentions(op['content'], term) and RESOLVED_PAT.search(op['content'])):
                    continue
                avail = [t for t in later if t <= step]  # PMA step k runs after receipt k
                findings.append({'rule': 'R1', 'source': 'PMA', 'term': term,
                                 'failure_turn': fr['turn'], 'closure_step': step,
                                 'tool': op['tool'],
                                 'kind': 'no_later_receipt' if not avail else 'needs_citation',
                                 'later_receipts_available': avail,
                                 'excerpt': op['content'][:240]})
            for prev, cur in zip(states, states[1:]):
                task_turn = cur['step'] + 1  # PoS step s digests receipt s+1
                if task_turn < fr['turn']:
                    continue
                removed = [g for g in prev['achievement'] + prev['epistemic']
                           if g not in cur['achievement'] + cur['epistemic'] and mentions(g, term)]
                if removed:
                    avail = [t for t in later if t <= task_turn]
                    findings.append({'rule': 'R1', 'source': 'PoS', 'term': term,
                                     'failure_turn': fr['turn'], 'closure_step': cur['step'],
                                     'kind': 'no_later_receipt' if not avail else 'needs_citation',
                                     'later_receipts_available': avail, 'removed_gaps': removed})
    return terms, fails, findings


def rule2(states, final_text, proposal):
    if not states:
        return {'fires': None, 'reason': 'no PoS states'}
    last = states[-1]
    gaps = last['achievement'] + last['epistemic']
    addressed = []
    for g in gaps:
        words = [w for w in re.findall(r'[A-Za-z/][\w./-]{3,}', g) if w.lower() not in STOP]
        hit = [w for w in words if mentions(final_text, w)]
        addressed.append({'gap': g, 'final_text_mentions': hit})
    return {'fires': bool(gaps), 'last_pos_step': last['step'],
            'proposal_turn': proposal['payload'].get('turn') if proposal else None,
            'open_gaps': addressed}


def main(runs):
    report = {}
    for run in runs:
        task_text, receipts, final_text, proposal = load_task(run)
        states = load_pos_states(run)
        pma_ops = load_pma_ops(run)
        terms, fails, findings = rule1(task_text, receipts, states, pma_ops)
        report[os.path.basename(run)] = {
            'receipts': len(receipts), 'pos_states': len(states), 'pma_ops': len(pma_ops),
            'requirement_terms': terms,
            'receipt_index': [{'turn': r['turn'], 'exit': r['exit_code'],
                               'script_head': r['script'][:160]} for r in receipts],
            'requirement_bound_failures': fails,
            'R1_findings': findings,
            'R2': rule2(states, final_text, proposal),
            'gap_timeline': [{'step': s['step'], 'a': s['achievement'], 'e': s['epistemic']}
                             for s in states],
        }
    json.dump(report, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
