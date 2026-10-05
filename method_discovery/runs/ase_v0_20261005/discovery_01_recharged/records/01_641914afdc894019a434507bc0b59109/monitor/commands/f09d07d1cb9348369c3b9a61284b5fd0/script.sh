
# Check if Target 5 client option files exist and are complete
echo "=== Target 5: Client Option Files ==="
ls -la /app/client/option*.go 2>&1
echo ""
echo "=== Checking for required Target 5 items ==="
echo "1. WithUnaryOptions, WithUnaryRPCTimeout, WithUnaryMiddleware:"
grep -l "WithUnaryOptions\|WithUnaryRPCTimeout\|WithUnaryMiddleware" /app/client/option*.go 2>/dev/null || echo "NOT FOUND"
echo ""
echo "2. WithStreamOptions, WithStreamRecvTimeout, WithStreamMiddleware:"
grep -l "WithStreamOptions\|WithStreamRecvTimeout" /app/client/option*.go 2>/dev/null || echo "NOT FOUND"
echo ""
echo "3. TailOption:"
grep -l "TailOption" /app/client/option.go 2>/dev/null || echo "NOT FOUND"
