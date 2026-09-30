
# Check current synopsis state
with open('/logs/agent/monitor/task_evidence/synopsis.jsonl', 'r') as f:
    lines = f.readlines()
    total = len(lines)
    print(f"Total synopsis lines: {total}")
    
    # Show last 12 entries to see recent progress
    print("\n=== Last 12 synopsis entries ===")
    for line in lines[-12:]:
        import json
        entry = json.loads(line)
        print(f"Cursor {entry['cursor']}, Turn {entry['task_turn']}: {entry['intent'][:120]}")
