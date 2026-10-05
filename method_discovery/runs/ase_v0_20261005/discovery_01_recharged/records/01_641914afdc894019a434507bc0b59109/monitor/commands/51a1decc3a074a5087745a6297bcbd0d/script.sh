
# Check specific build errors
echo "=== BUILD ERROR DETAILS ==="
echo ""
echo "1. TailOption redeclaration:"
echo "   Line 65:"
sed -n '65,67p' /app/client/option.go
echo "   Line 88:"
sed -n '88,90p' /app/client/option.go
echo ""
echo "2. StreamXOpts undefined - checking if it exists in internal/client:"
grep -n "StreamXOpts\|StreamOptions" /app/internal/client/option.go | head -5
echo ""
echo "3. streamx package check:"
ls -la /app/pkg/streamx/ 2>&1 | head -5
