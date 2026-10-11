
# Check Target 5 requirement 7 - Retry field migration (CRITICAL)
echo "=== Target 5 Req 7: Checking if retry fields migrated to o.UnaryOptions.* ==="
grep -n "o\.UnaryOptions\.RetryMethodPolicies\|o\.UnaryOptions\.RetryContainer\|o\.UnaryOptions\.Fallback" /app/client/option.go | head -10
echo "---"
echo "=== Checking if OLD fields still being used (should be NONE) ==="
grep -n "o\.RetryMethodPolicies\[" /app/client/option.go | grep -v "UnaryOptions" | head -5
