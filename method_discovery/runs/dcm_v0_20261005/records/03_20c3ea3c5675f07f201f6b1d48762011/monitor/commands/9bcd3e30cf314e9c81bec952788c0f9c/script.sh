
# Verify Target 5 implementation completeness
echo "=== 1. Type aliases in client/option.go ==="
grep -n "type.*Option.*=" /app/client/option.go | grep -E "(Unary|Stream|TTHeader)" | head -5

echo ""
echo "=== 2. TailOption function exists ==="
grep -n "func TailOption" /app/client/option.go

echo ""
echo "=== 3. WithRecvTimeout in callopt/options.go ==="
grep -n "func WithRecvTimeout" /app/client/callopt/options.go

echo ""
echo "=== 4. WithRecvTimeout in streamcall ==="
grep -n "func WithRecvTimeout" /app/client/callopt/streamcall/call_options.go

echo ""
echo "=== 5. UnaryOptions struct with RetryMethodPolicies ==="
grep -A3 "type UnaryOptions struct" /app/internal/client/option.go

echo ""
echo "=== 6. WithFailureRetry uses o.Unary.RetryMethodPolicies ==="
grep -A5 "func WithFailureRetry" /app/client/option.go | grep -E "(Unary|RetryMethodPolicies)"

echo ""
echo "=== 7. Final build verification ==="
cd /app && go build ./... 2>&1 | head -20
