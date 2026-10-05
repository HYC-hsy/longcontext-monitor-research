
# Check if retry functions were migrated by looking at the unaryOpt pattern
echo "=== RETRY MIGRATION VERIFICATION ==="
echo ""
echo "Pattern to look for: unaryOpt func that sets opts.RetryMethodPolicies or opts.Fallback"
echo "                    then appends to o.UnaryOptions"
echo ""

echo "1. WithFailureRetry structure:"
grep -A15 "func WithFailureRetry" /app/client/option.go 2>/dev/null | head -20

echo ""
echo "2. WithSpecifiedResultRetry (already migrated per synopsis):"
grep -A8 "func WithSpecifiedResultRetry" /app/client/option.go 2>/dev/null | grep -E "(unaryOpt|UnaryOptions|RetryWithResult)" | head -5
