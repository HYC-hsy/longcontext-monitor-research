
# Check current synopsis state
with open('/logs/agent/monitor/task_evidence/synopsis.jsonl', 'r') as f:
    lines = f.readlines()
    total = len(lines)
    print(f"Total synopsis lines: {total}")
    
    # Show entries from cursor 122 onward to see response to intervention
    print("\n=== Synopsis from intervention point (cursor 122+) ===")
    for line in lines[121:]:  # cursor 122 is index 121
        import json
        entry = json.loads(line)
        print(f"Cursor {entry['cursor']}, Turn {entry['task_turn']}: {entry['intent'][:120]}")
