
# Verify the 3 function migrations are correct
echo "=== VERIFICATION: Target 5 Req 7 - Retry/Fallback Field Migration ==="
echo ""
echo "1. WithRetryContainer (should use o.UnaryOptions.RetryContainer):"
grep -A 10 "^func WithRetryContainer" /app/client/option_advanced.go | grep -E "RetryContainer|UnaryOptions"
echo ""
echo "2. WithFallback (should use o.UnaryOptions.Fallback):"
grep -A 8 "^func WithFallback" /app/client/option.go | grep -E "Fallback|UnaryOptions"
echo ""
echo "3. WithSpecifiedResultRetry (should use o.UnaryOptions.RetryWithResult):"
grep -A 8 "^func WithSpecifiedResultRetry" /app/client/option.go | grep -E "RetryWithResult|UnaryOptions"
