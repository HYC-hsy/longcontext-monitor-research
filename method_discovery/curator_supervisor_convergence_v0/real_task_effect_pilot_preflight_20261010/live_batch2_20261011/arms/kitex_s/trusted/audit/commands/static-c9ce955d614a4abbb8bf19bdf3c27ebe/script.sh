
# Also check if streamcall location has been addressed
echo "=== Checking streamcall.go location (critical issue) ==="
ls -la /app/callopt/streamcall.go 2>/dev/null && echo "ERROR: Still in wrong location"
ls -la /app/client/callopt/streamcall/recv_timeout.go 2>/dev/null && echo "GOOD: Added to correct location"
