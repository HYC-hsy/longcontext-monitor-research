
# Verify requirement 7: WithFailureRetry migration to o.Unary.RetryMethodPolicies
echo "=== Checking WithFailureRetry implementation ==="
grep -A15 "func WithFailureRetry" /app/client/option.go | grep -E "(Unary|RetryMethodPolicies|func WithFailureRetry)"

echo ""
echo "=== Checking if old storage location is still used ==="
grep -n "o.RetryMethodPolicies\[" /app/client/option.go | head -3

echo ""
echo "=== Verifying UnaryOptions is used ==="
grep -n "o.Unary.RetryMethodPolicies" /app/client/option.go | head -3

echo ""
echo "=== Check all files mentioned in Target 5 exist ==="
ls -la /app/client/option_unary.go /app/client/option_stream.go /app/client/option_ttstream.go 2>&1 | grep -v "cannot access"

echo ""
echo "=== Verify final state summary ==="
echo "Target 1: pkg/streaming/types.go exists?"
test -f /app/pkg/streaming/types.go && echo "✓ YES" || echo "✗ NO"

echo "Target 2: cep/sep packages exist?"
test -d /app/pkg/endpoint/cep && test -d /app/pkg/endpoint/sep && echo "✓ YES" || echo "✗ NO"

echo "Target 3: Protocol constants correct?"
grep -q "TTHeaderStreaming Protocol = 64" /app/transport/keys.go && echo "✓ YES" || echo "✗ NO"

echo "Target 6: Dump() method exists?"
grep -q "func.*Dump" /app/pkg/remote/trans/nphttp2/conn_pool.go && echo "✓ YES" || echo "✗ NO"
