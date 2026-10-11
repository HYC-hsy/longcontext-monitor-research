
# Verify Target 5 Req 7: Retry fields migrated to o.UnaryOptions.RetryMethodPolicies
echo "=== Target 5 Req 7: Retry migration check ==="
echo "Should have: o.UnaryOptions.RetryMethodPolicies"
grep -n "o\.UnaryOptions\.RetryMethodPolicies" /app/client/option.go | head -5
echo ""
echo "=== Should NOT have old location (o.RetryMethodPolicies direct access) ==="
grep -n "^\s*o\.RetryMethodPolicies\[" /app/client/option.go | head -5 || echo "✓ No direct access to old location"
