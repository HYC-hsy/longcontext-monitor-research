
# Check if there are any recent changes or git status
cd /app && git log --oneline -5 2>&1 || echo "No git history"
echo "---"
# Check if task agent has created any files
ls -la /logs/agent/monitor/task_evidence/ 2>&1 | head -20
