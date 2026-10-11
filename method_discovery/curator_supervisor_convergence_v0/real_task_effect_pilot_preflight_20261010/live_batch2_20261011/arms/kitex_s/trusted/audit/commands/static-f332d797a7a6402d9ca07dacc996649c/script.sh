
# Check if streamcall was moved to correct location
ls -la /app/client/callopt/streamcall/*.go 2>/dev/null | grep -E "recv_timeout|streamcall" 
echo "---"
ls -la /app/callopt/streamcall.go 2>/dev/null && echo "Still in wrong location"
