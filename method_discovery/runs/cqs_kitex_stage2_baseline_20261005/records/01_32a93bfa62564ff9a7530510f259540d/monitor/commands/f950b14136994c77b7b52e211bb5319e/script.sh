
# Verify WithFailureRetry and WithBackupRequest now use o.UnaryOptions.RetryMethodPolicies
grep -A 15 "func WithFailureRetry" /app/client/option.go | grep -E "(UnaryOptions|RetryMethodPolicies)"
