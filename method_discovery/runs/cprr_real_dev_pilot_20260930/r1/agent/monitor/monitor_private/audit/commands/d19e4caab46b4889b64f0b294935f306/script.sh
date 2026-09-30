
# Count total lines in synopsis and public_events
wc -l /logs/agent/monitor/task_evidence/synopsis.jsonl
wc -l /logs/agent/monitor/task_evidence/public_events.jsonl

# Check what the latest cursor and turn are
tail -1 /logs/agent/monitor/task_evidence/synopsis.jsonl | python3 -c "import json, sys; data=json.load(sys.stdin); print(f\"Latest cursor: {data['cursor']}, turn: {data['task_turn']}, boundary: {data['boundary']}\")"
