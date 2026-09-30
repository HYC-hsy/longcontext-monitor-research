
# Check if there are any monitor logs or delivery feedback
ls -la /logs/agent/monitor/ 2>&1

# Check for any recent activity indicators
ls -la /logs/agent/monitor/monitor_private/ 2>&1

# See if task agent has any active state
find /logs -type f -name "*.jsonl" 2>&1 | head -10
