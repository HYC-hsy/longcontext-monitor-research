
# Check if existing WithFailureRetry was modified to use UnaryOptions.RetryMethodPolicies
grep -A 5 "func WithFailureRetry" /app/client/option.go
