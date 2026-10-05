
# Check the build output that's currently running
session_id="d0f3c34e64ab4c27b6a341d1f72fbca5"
if [ -f "/logs/agent/monitor/monitor_private/audit/commands/${session_id}/output.log" ]; then
  cat "/logs/agent/monitor/monitor_private/audit/commands/${session_id}/output.log"
else
  echo "Build still running or output not yet available"
fi
