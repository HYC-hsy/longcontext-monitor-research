
# Verify Target 5 retry field migrations
echo "=== Checking retry field migrations (should store in o.UnaryOptions.*) ==="
grep -n "o.UnaryOptions.Retry\|o.UnaryOptions.Fallback" /app/client/option.go | head -10
echo "---"
# Check if old retry fields still used
grep -n "o.RetryMethodPolicies\|o.RetryContainer\|^[^/]*o.Fallback[^a-zA-Z]" /app/client/option.go | grep -v "UnaryOptions" | head -5
