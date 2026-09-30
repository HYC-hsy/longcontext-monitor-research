
# Check the total number of lines in synopsis to know how far to read
with open('/logs/agent/monitor/task_evidence/synopsis.jsonl', 'r') as f:
    lines = f.readlines()
    total = len(lines)
    print(f"Total synopsis lines: {total}")
    
    # Show last few entries to see current state
    print("\n=== Last 3 synopsis entries ===")
    for line in lines[-3:]:
        import json
        entry = json.loads(line)
        print(f"Cursor {entry['cursor']}, Turn {entry['task_turn']}: {entry['intent'][:100]}")
