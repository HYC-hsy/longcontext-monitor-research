
# Check retry options migration to o.UnaryOptions
grep -A 2 "WithFailureRetry" /app/client/option.go | grep -E "(RetryMethodPolicies|UnaryOptions)"
grep -A 2 "WithBackupRequest" /app/client/option.go | grep -E "(RetryMethodPolicies|UnaryOptions)"
grep -A 2 "WithRetryContainer" /app/client/option_advanced.go | grep -E "(RetryContainer|UnaryOptions)"
