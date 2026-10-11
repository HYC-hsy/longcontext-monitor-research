
# Search for the specific functions mentioned in Target 5 Req 7
echo "=== Checking Target 5 Req 7: Five functions that must migrate ==="
echo ""
echo "1. WithRetryContainer - should use o.UnaryOptions.RetryContainer:"
grep -A 10 "^func WithRetryContainer" /app/client/option.go | grep -E "RetryContainer|UnaryOptions"
echo ""
echo "2. WithFallback - should use o.UnaryOptions.Fallback:"
grep -A 10 "^func WithFallback" /app/client/option.go | grep -E "Fallback|UnaryOptions"
echo ""
echo "3. WithSpecifiedResultRetry - should use o.UnaryOptions.RetryWithResult:"
grep -A 10 "^func WithSpecifiedResultRetry" /app/client/option.go | grep -E "RetryWithResult|UnaryOptions"
