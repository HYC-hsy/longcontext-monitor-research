
# Check Target 5 retry field migration status
echo "=== Target 5: Check if retry fields use NEW location o.UnaryOptions.* ==="
grep -n "o\.UnaryOptions\.RetryMethodPolicies\|o\.UnaryOptions\.RetryContainer" /app/client/option.go | head -5
echo "---"
echo "=== OLD location (should be NONE) ==="
grep -n "o\.RetryMethodPolicies\[" /app/client/option.go | grep -v "//" | head -3
