
# Check if WithFailureRetry and WithBackupRequest now append to o.UnaryOptions
echo "=== FINAL RETRY MIGRATION VERIFICATION ==="
echo ""
echo "Checking if retry functions append to o.UnaryOptions (required by spec):"
echo ""

echo "1. WithFailureRetry - checking for 'o.UnaryOptions = append':"
grep -A20 "func WithFailureRetry" /app/client/option.go 2>/dev/null | grep "o.UnaryOptions" || echo "   ✗ NOT FOUND - NOT migrated"

echo ""
echo "2. WithBackupRequest - checking for 'o.UnaryOptions = append':"
grep -A20 "func WithBackupRequest" /app/client/option.go 2>/dev/null | grep "o.UnaryOptions" || echo "   ✗ NOT FOUND - NOT migrated"

echo ""
echo "3. WithFallback - checking for 'o.UnaryOptions = append':"
grep -A15 "func WithFallback" /app/client/option.go 2>/dev/null | grep "o.UnaryOptions" || echo "   ✗ NOT FOUND - NOT migrated"

echo ""
echo "4. WithSpecifiedResultRetry - checking for 'o.UnaryOptions = append':"
grep -A10 "func WithSpecifiedResultRetry" /app/client/option.go 2>/dev/null | grep "o.UnaryOptions"

echo ""
echo "SUMMARY:"
echo "The spec requirement states retry functions must store in o.UnaryOptions.RetryMethodPolicies"
echo "This means: unaryOpt func sets opts.RetryMethodPolicies, then o.UnaryOptions = append(o.UnaryOptions, unaryOpt)"
echo ""
echo "Current implementation: WithFailureRetry creates unaryOpt func but doesn't append to o.UnaryOptions"
echo "Status: Requirement 7 - INCOMPLETE (migration pattern not followed)"
