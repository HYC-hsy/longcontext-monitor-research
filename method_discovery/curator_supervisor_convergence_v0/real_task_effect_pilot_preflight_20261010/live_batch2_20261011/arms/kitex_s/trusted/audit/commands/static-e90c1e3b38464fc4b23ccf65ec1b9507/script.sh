
# Check all functions in option.go that should be migrated per Target 5 Req 7
echo "=== Target 5 Req 7: All 5 functions that must migrate ==="
echo "Required: WithFailureRetry, WithBackupRequest, WithRetryContainer, WithFallback, WithSpecifiedResultRetry"
echo ""
for func in WithFailureRetry WithBackupRequest WithMixedRetry WithRetryContainer WithFallback WithSpecifiedResultRetry; do
    echo "=== $func ==="
    awk "/^func $func/,/^}/" /app/client/option.go | grep "RetryMethodPolicies\|RetryContainer\|Fallback" | head -3
done
