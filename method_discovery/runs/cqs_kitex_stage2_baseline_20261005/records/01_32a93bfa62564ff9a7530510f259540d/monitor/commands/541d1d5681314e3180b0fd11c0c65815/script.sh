
# Check Target 5 requirement 7: WithFailureRetry must store in o.UnaryOptions.RetryMethodPolicies
grep -A 10 "func WithFailureRetry" /app/client/option.go | head -15
