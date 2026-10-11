
# Verify streamcall.go location - critical issue
echo "=== Checking streamcall.go location ==="
ls -la /app/callopt/streamcall.go 2>/dev/null && echo "ERROR: File at wrong location - should be in client/callopt/streamcall/"
ls -la /app/client/callopt/streamcall/*.go 2>/dev/null | grep "streamcall.go" && echo "Correct: File in client/callopt/streamcall/"
echo ""
# Check if WithRecvTimeout exists in the right place
grep -rn "func WithRecvTimeout" /app/client/callopt/streamcall/ 2>/dev/null || echo "WithRecvTimeout not found in correct location"
