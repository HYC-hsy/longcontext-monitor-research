
# Verify Target 5 - check for all required functions
echo "Checking required Target 5 functions:"
echo "=== WithUnaryRPCTimeout ==="
grep -n "WithUnaryRPCTimeout" /app/client/*.go 2>/dev/null || echo "NOT FOUND"
echo "=== WithStreamRecvTimeout ==="
grep -n "WithStreamRecvTimeout" /app/client/*.go 2>/dev/null || echo "NOT FOUND"
echo "=== TailOption ==="
grep -n "func TailOption" /app/client/*.go 2>/dev/null || echo "NOT FOUND"
echo "=== streamcall package ==="
find /app/client/callopt -type d -name "streamcall" 2>/dev/null || echo "NOT FOUND"
