
# Check if streamcall directory exists with WithRecvTimeout
if [ -d /app/client/callopt/streamcall ]; then
    grep -n "WithRecvTimeout" /app/client/callopt/streamcall/*.go 2>/dev/null || echo "MISSING: WithRecvTimeout not found in streamcall"
else
    echo "MISSING: client/callopt/streamcall directory does not exist"
fi
