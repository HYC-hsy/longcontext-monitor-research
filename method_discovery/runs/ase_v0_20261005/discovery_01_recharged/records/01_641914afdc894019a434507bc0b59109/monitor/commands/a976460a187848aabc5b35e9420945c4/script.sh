
# Read the build result from turn 214
session_id="981abba385fa4946b3276e3d4f0fe397"
if [ -f "/logs/agent/monitor/monitor_private/audit/commands/${session_id}/output.log" ]; then
  tail -50 "/logs/agent/monitor/monitor_private/audit/commands/${session_id}/output.log"
else
  echo "Build output not found in expected location"
fi
