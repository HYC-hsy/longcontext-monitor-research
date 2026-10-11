
# Check what's at lines 369 and 391 in client/option.go (still using old location)
echo "=== Line 369 and context (WithMixedRetry?) ==="
sed -n '360,375p' /app/client/option.go | grep -n "o\.RetryMethodPolicies"
echo ""
echo "=== Line 391 and context ==="
sed -n '385,400p' /app/client/option.go | grep -n "o\.RetryMethodPolicies"
echo ""
echo "=== All functions that should be migrated per task req 7 ==="
echo "WithFailureRetry, WithBackupRequest, WithRetryContainer, WithFallback, WithSpecifiedResultRetry"
