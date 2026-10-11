
# TARGET 5 VERIFICATION: Check ALL retry functions migrated
echo "=== Target 5: Checking if ALL retry functions use UnaryOptions ==="
echo "Lines 369 and 391 were problematic before (WithMixedRetry and WithRetryMethodPolicies)"
echo ""
echo "Line 369 context (should be o.UnaryOptions.RetryMethodPolicies):"
sed -n '366,372p' /app/client/option.go
echo ""
echo "Line 391 context (should be o.UnaryOptions.RetryMethodPolicies):"
sed -n '388,395p' /app/client/option.go
