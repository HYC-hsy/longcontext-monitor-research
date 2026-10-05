
# Detailed check of retry migration requirement
echo "=== TARGET 5 REQUIREMENT 7: Retry Migration Status ==="
echo ""
echo "The spec says:"
echo "  'The existing WithFailureRetry and WithBackupRequest options must store"
echo "   retry policies in o.UnaryOptions.RetryMethodPolicies (not the old o.RetryMethodPolicies)'"
echo ""
echo "Checking current implementation:"
echo ""
echo "1. WithFailureRetry:"
grep -A10 "func WithFailureRetry" /app/client/option.go 2>/dev/null | grep -E "(RetryMethodPolicies|UnaryOptions)" | head -3

echo ""
echo "2. WithBackupRequest:"  
grep -A10 "func WithBackupRequest" /app/client/option.go 2>/dev/null | grep -E "(RetryMethodPolicies|UnaryOptions)" | head -3

echo ""
echo "3. WithRetryContainer:"
grep -A10 "func WithRetryContainer" /app/client/option.go 2>/dev/null | grep -E "(RetryContainer|UnaryOptions)" | head -3

echo ""
echo "4. WithFallback:"
grep -A10 "func WithFallback" /app/client/option.go 2>/dev/null | grep -E "(Fallback|UnaryOptions)" | head -3

echo ""
echo "5. WithSpecifiedResultRetry:"
grep -A10 "func WithSpecifiedResultRetry" /app/client/option.go 2>/dev/null | grep -E "(RetryWithResult|UnaryOptions)" | head -3
