"""Replay public saved P2 payloads only; no research_events or model access."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'))
from selection_context import digest, project_steps, render_selection


def replay(path):
    report = []
    for line in Path(path).read_text().splitlines():
        record = json.loads(line)
        if record['phase'] != 'selection':
            continue
        prompt, entries = record['prompt'], []
        # Offline inversion of the saved upstream formatter, not a production parser.
        for match in re.finditer(r'\[Step ([0-9]+)\]', prompt):
            start = match.end()
            command_start = prompt.index('\nCommands Executed: ', start)
            output_start = prompt.index('\nTerminal Output: ', command_start)
            command_text = prompt[command_start + len('\nCommands Executed: '):output_start]
            commands = []
            while command_text:
                _, end = json.JSONDecoder().raw_decode(command_text)
                commands.append(command_text[:end])
                command_text = command_text[end:].removeprefix('; ')
            _, end = json.JSONDecoder().raw_decode(prompt[output_start + len('\nTerminal Output: '):])
            observation = prompt[output_start + len('\nTerminal Output: '):][:end]
            entries.append(dict(step=int(match[1]), analysis=prompt[start:command_start].removeprefix('\nAgent Analysis: '),
                                commands=commands, observation=observation))
        catalogue, _ = json.JSONDecoder().raw_decode(prompt.split('## Selectable catalogue\n', 1)[1])
        status = prompt.split('<status>', 1)[1].split('</status>', 1)[0]
        for item in catalogue[1:]:
            key = re.search(r'\[([^\[\]\n]+)\] ' + re.escape(item['content']), prompt)[1]
            item['binding'] = re.search(r'\[' + re.escape(key) + r'\] (content_status=[^\n]+)', prompt)[1]
        binding = prompt.split('Status binding: ', 1)[1].split('\n', 1)[0] if 'Status binding: ' in prompt else 'legacy memory; binding not recorded; not semantic proof'
        rows, audit = project_steps(entries)
        after = render_selection(catalogue, status, rows, record['cycle_step'], binding)
        for old, new in zip(entries, rows):
            assert old['commands'] == new['commands'] and old['analysis'] == new['analysis']
            assert json.loads(old['observation'])['tool_results'] == new['observation']['tool_results']
        report.append(dict(cycle=record['cycle_step'], before=len(prompt), after=len(after),
                           before_sha256=digest(prompt), after_sha256=digest(after), audit=audit,
                           working_memory_counts=[prompt.count('[WORKING MEMORY]'), after.count('[WORKING MEMORY]')],
                           task_first_line_counts=[prompt.count(catalogue[0]['content'].splitlines()[0]),
                                                   after.count(catalogue[0]['content'].splitlines()[0])]))
    return report


if __name__ == '__main__':
    print(json.dumps(replay(sys.argv[1]), ensure_ascii=False, indent=2))
