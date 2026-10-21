"""Receipt-justified failure ledger (RJC-v0, invariants I1 and I2).

Mechanical bookkeeping over GA tool receipts. No model calls and no semantic
judgement. A failure record opens from an executed command receipt. It closes
only from a LATER executed command receipt that invokes the same command word,
exits 0 and shows no failure line. Model text, PoS gap removal and PMA memory
writes never close a record. Every closure keeps the failing script, the
failure lines, the closing script and the closing stdout head side by side so
that any later judge sees both invocation contexts.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

LIMITS = {'panel_chars': 2000, 'review_chars': 2000, 'completion_chars': 4000,
          'fail_lines': 3, 'script_head': 240, 'stdout_head': 160}

FAIL_LINE = re.compile(r'command not found|No such file or directory|Permission denied|'
                       r'^(?:bash: )?(?:line \d+: )?.*?\b(?:error|Error|ERROR)\b[: ]', re.M)
CMD_NOT_FOUND = re.compile(r'(?:bash: )?(?:line \d+: )?(?P<cmd>[\w.+-]+): command not found')
SHELL_WORDS = frozenset("""cd echo export cat ls then fi if do done for in set true false
EOF bash sh sudo env exit elif else while case esac return printf test [ ]""".split())
GOAL_STOP = frozenset("""with make available compile compiled instrumentation source
sources snapshot vendored pre-vendored instead fetching over network the and use
used using into from that this will should must have been your also only""".split())


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _digest(text):
    return hashlib.sha256(str(text).encode('utf-8')).hexdigest()


def script_of(arguments):
    if not isinstance(arguments, dict):
        return ''
    value = arguments.get('script') or arguments.get('code')
    return value if isinstance(value, str) else _json(arguments)


WRAPPERS = frozenset({'sudo', 'env', 'nohup', 'time'})
LOOKUP_WORDS = frozenset({'which', 'command', 'type', 'hash', 'whereis'})
INNER_SHELL_PATTERN = r"""^(?:bash|sh|zsh|dash)\b[^'"]*-l?c\s+(?:'([^']*)'|"([^"]*)")"""
INNER_SHELL = re.compile(INNER_SHELL_PATTERN)


def command_tokens(script, _depth=0):
    """Words in command position of each simple command; shell keywords excluded.

    `bash -c '...'` and `sh -c "..."` wrappers contribute the commands of their
    quoted body, so a login-shell invocation still counts as invoking the command.
    The wrapper itself is kept visible through the stored script head.
    """
    tokens = set()
    for line in script.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        inner = INNER_SHELL.match(line)
        if inner and _depth < 2:
            tokens |= command_tokens(inner.group(1) or inner.group(2) or '', _depth + 1)
            continue
        for part in re.split(r'[|;&]+', line):
            words = part.strip().split()
            while words and words[0] in WRAPPERS:
                words = words[1:]
            if not words or words[0] in SHELL_WORDS or not re.match(r'^[\w./+-]+$', words[0]):
                continue
            tokens.add(os.path.basename(words[0]))
            if words[0] in LOOKUP_WORDS:
                # `which X` / `command -v X` are PATH-resolution probes of X.
                tokens |= {os.path.basename(word) for word in words[1:]
                           if not word.startswith('-') and re.match(r'^[\w./+-]+$', word)}
    return tokens


def failure_lines(text):
    return [line for line in text.splitlines() if FAIL_LINE.search(line)]


def failure_tokens(text):
    return {match.group('cmd') for match in CMD_NOT_FOUND.finditer(text)}


def goal_tokens(goal_text):
    tokens = set()
    for word in re.findall(r'[A-Za-z][\w-]{2,}', goal_text or ''):
        lowered = word.lower()
        if lowered not in GOAL_STOP:
            tokens.add(lowered)
    return tokens


def goal_relevant(tokens, goal):
    for token in tokens:
        lowered = token.lower()
        if any(len(g) >= 4 and (g in lowered or lowered in g) for g in goal):
            return True
    return False


def _head(text, limit):
    text = str(text or '')
    return text if len(text) <= limit else text[:limit] + f'...[+{len(text) - limit} chars]'


def invocation_lines(script, tokens, *, limit=3, width=160):
    """Script lines whose command-position words include one of the tokens."""
    wanted = set(tokens)
    lines = []
    for line in script.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and command_tokens(stripped) & wanted:
            lines.append(_head(stripped, width))
            if len(lines) == limit:
                break
    return lines


class FailureLedger:
    """Episode-local, append-only ledger of command failures and receipt closures."""

    def __init__(self, goal_text):
        self.goal_text = goal_text or ''
        self.goal = goal_tokens(goal_text)
        self.records = []
        self.version = 0
        self.history = []

    # -- ingestion -----------------------------------------------------------

    @staticmethod
    def _receipts(action_batch, source_events):
        actions = {}
        for index, action in enumerate(action_batch or ()):
            if isinstance(action, dict):
                actions[str(action.get('id', ''))] = (index, action)
        receipts = []
        for source in source_events or ():
            if not isinstance(source, dict):
                continue
            tool_id = str(source.get('tool_use_id') or source.get('event_id') or '')
            index, action = actions.get(tool_id, (len(actions), {}))
            result = source.get('result') if isinstance(source.get('result'), dict) else {}
            receipts.append({'order': index, 'id': tool_id,
                             'name': action.get('name') or source.get('name'),
                             'script': script_of(action.get('arguments')),
                             'stdout': str(result.get('stdout', '')),
                             'stderr': str(result.get('stderr', '')),
                             'exit_code': result.get('exit_code'),
                             'status': result.get('status')})
        return sorted(receipts, key=lambda item: item['order'])

    def ingest(self, *, turn, transition_id, action_batch, source_events):
        opened, closed = [], []
        for receipt in self._receipts(action_batch, source_events):
            if receipt['name'] != 'code_run':
                continue
            text = receipt['stdout'] + '\n' + receipt['stderr']
            lines = failure_lines(text)
            clean_success = receipt['exit_code'] in (0, None) and not lines and (
                receipt['status'] in (None, 'success'))
            if clean_success:
                invoked = command_tokens(receipt['script'])
                for record in self.records:
                    if record['closed_by'] is not None or record['turn'] >= turn:
                        continue
                    hit = sorted(token for token in record['tokens'] if token in invoked)
                    if hit:
                        record['closed_by'] = {
                            'turn': turn, 'receipt_id': receipt['id'], 'tokens': hit,
                            'closing_script_sha256': _digest(receipt['script']),
                            'closing_invocation_lines': invocation_lines(receipt['script'], hit),
                            'closing_script_head': _head(receipt['script'].strip(),
                                                         LIMITS['script_head']),
                            'closing_stdout_head': _head(receipt['stdout'].strip(),
                                                         LIMITS['stdout_head'])}
                        closed.append(record['failure_id'])
                continue
            failed = receipt['exit_code'] not in (0, None) or bool(lines)
            if not failed:
                continue
            tokens = failure_tokens(text) or command_tokens(receipt['script'])
            record = {'failure_id': f'F{len(self.records) + 1}', 'turn': turn,
                      'transition_id': transition_id, 'receipt_id': receipt['id'],
                      'exit_code': receipt['exit_code'], 'tokens': sorted(tokens),
                      'fail_lines': lines[:LIMITS['fail_lines']],
                      'failing_script_sha256': _digest(receipt['script']),
                      'failing_invocation_lines': invocation_lines(receipt['script'], tokens),
                      'failing_script_head': _head(receipt['script'].strip(),
                                                   LIMITS['script_head']),
                      'goal_relevant': goal_relevant(tokens, self.goal),
                      'closed_by': None}
            self.records.append(record)
            opened.append(record['failure_id'])
        if opened or closed:
            self.version += 1
        summary = {'turn': turn, 'transition_id': transition_id,
                   'opened': opened, 'closed': closed, 'ledger_version': self.version}
        self.history.append(summary)
        return summary

    # -- queries -------------------------------------------------------------

    def open_records(self, *, goal_relevant_only=True):
        return [record for record in self.records if record['closed_by'] is None
                and (record['goal_relevant'] or not goal_relevant_only)]

    def closures(self, *, goal_relevant_only=True):
        return [record for record in self.records if record['closed_by'] is not None
                and (record['goal_relevant'] or not goal_relevant_only)]

    def tag_for_now(self):
        return [record['failure_id'] for record in self.open_records()]

    @staticmethod
    def _view(record):
        view = {key: record[key] for key in ('failure_id', 'turn', 'receipt_id', 'exit_code',
                                             'tokens', 'fail_lines', 'failing_invocation_lines',
                                             'goal_relevant')}
        view['status'] = 'open' if record['closed_by'] is None else 'closed_by_receipt'
        if record['closed_by'] is not None:
            # The displayed pairing shows the two invocation contexts side by side;
            # full script heads and hashes stay in the ledger snapshot.
            view['closed_by'] = {key: record['closed_by'][key] for key in
                                 ('turn', 'receipt_id', 'tokens', 'closing_invocation_lines',
                                  'closing_stdout_head')}
        return view

    @staticmethod
    def _fit(items, cap, envelope):
        """Keep leading items while the serialized envelope stays within cap."""
        kept = []
        for item in items:
            trial = {**envelope, 'items': [*kept, item], 'omitted': len(items) - len(kept) - 1}
            if len(_json(trial)) > cap:
                break
            kept.append(item)
        return kept, len(items) - len(kept)

    def panel_section(self):
        items = ([self._view(r) for r in self.open_records()] +
                 [self._view(r) for r in self.closures()])
        if not items:
            return ''
        envelope = {'meaning': 'Mechanical receipt ledger for task-relevant command '
                               'failures. A closure only records that a later receipt '
                               'invoked the same command successfully; compare the two '
                               'scripts yourself. Not a verdict, not a new requirement.'}
        kept, omitted = self._fit(items, LIMITS['panel_chars'], envelope)
        return ('Receipt ledger (goal-relevant failures and their receipt closures):\n' +
                _json({**envelope, 'items': kept, 'omitted': omitted}))

    def closure_review(self, removed_gaps, *, step=None):
        open_items = [self._view(r) for r in self.open_records()]
        closures = [self._view(r) for r in self.closures()]
        if not removed_gaps and not open_items:
            return None
        envelope = {'protocol': 'rjc-closure-review-v0', 'step': step,
                    'removed_gaps': list(removed_gaps),
                    'instruction': 'Each removed gap needs a cited evidence_id and quote '
                                   'from a visible tool fragment that closes it. A '
                                   'removal supported only by belief text or memory '
                                   'prose is an issue of type unsupported_closure. Open '
                                   'failures below are mechanical facts, not verdicts; '
                                   'closures show both invocation scripts for comparison.'}
        kept, omitted = self._fit([*open_items, *closures], LIMITS['review_chars'], envelope)
        return {**envelope, 'items': kept, 'omitted': omitted}

    def completion_review(self, *, open_gaps, stale, state_version=None):
        open_items = [self._view(r) for r in self.open_records()]
        closures = [self._view(r) for r in self.closures()]
        fires = bool(open_gaps) or bool(open_items)
        envelope = {'protocol': 'rjc-completion-review-v0', 'fires': fires,
                    'state_version': state_version, 'state_may_be_stale': bool(stale),
                    'open_gaps': list(open_gaps)}
        kept, omitted = self._fit([*open_items, *closures], LIMITS['completion_chars'],
                                  envelope)
        review = {**envelope, 'items': kept, 'omitted': omitted}
        if fires:
            review['prompt'] = (
                'Before this episode can end, address each item below exactly once. For '
                'every open gap: cite one tool_use_id from your own receipts whose output '
                'closes it, or run a new command that would, or mark it UNRESOLVED. This '
                'checklist is derived mechanically from the auxiliary PoS state and your '
                'tool receipts; it is not a new requirement and does not judge '
                'correctness.\n' + _json(review))
        return review

    def snapshot(self):
        return {'protocol': 'rjc-failure-ledger-v0', 'version': self.version,
                'goal_tokens': sorted(self.goal), 'records': [dict(r) for r in self.records],
                'history': list(self.history)}
