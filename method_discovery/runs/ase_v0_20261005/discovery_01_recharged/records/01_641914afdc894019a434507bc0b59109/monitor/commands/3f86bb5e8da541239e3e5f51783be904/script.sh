
# Comprehensive Target 5 verification (Turn 100)
echo "=== TARGET 5 VERIFICATION AGAINST SPEC (Turn 100) ==="
echo ""

echo "SPEC REQUIREMENT 1: Type aliases in client/option.go"
grep -E "^type (UnaryOption|StreamOption|TTHeaderStreamingOption)" /app/client/option.go | wc -l | xargs echo "  Found:"
echo "  Required: 6 (UnaryOption, UnaryOptions, StreamOption, StreamOptions, TTHeaderStreamingOption, TTHeaderStreamingOptions)"

echo ""
echo "SPEC REQUIREMENT 2: client/option_unary.go with 4 functions"
[ -f "/app/client/option_unary.go" ] && echo "  ✓ File exists" || echo "  ✗ File missing"
grep "^func With" /app/client/option_unary.go 2>/dev/null | wc -l | xargs echo "  Functions:"

echo ""
echo "SPEC REQUIREMENT 3: client/option_stream.go with 8 functions"
[ -f "/app/client/option_stream.go" ] && echo "  ✓ File exists" || echo "  ✗ File missing"
echo "  Required: WithStreamOptions, WithStreamRecvTimeout, WithStreamMiddleware,"
echo "            WithStreamMiddlewareBuilder, WithStreamRecvMiddleware,"
echo "            WithStreamRecvMiddlewareBuilder, WithStreamSendMiddleware,"
echo "            WithStreamSendMiddlewareBuilder"
echo "  Actual functions:"
grep "^func With" /app/client/option_stream.go 2>/dev/null || echo "  ERROR: Cannot read file"

echo ""
echo "SPEC REQUIREMENT 4: client/option_ttstream.go with 2 functions"
[ -f "/app/client/option_ttstream.go" ] && echo "  ✓ File exists" || echo "  ✗ File missing"
grep "^func With" /app/client/option_ttstream.go 2>/dev/null | wc -l | xargs echo "  Functions:"

echo ""
echo "SPEC REQUIREMENT 5: TailOption function in client/option.go"
grep -c "^func TailOption" /app/client/option.go 2>/dev/null | xargs echo "  Found:"

echo ""
echo "SPEC REQUIREMENT 6: WithRecvTimeout in client/callopt/streamcall"
grep -c "^func WithRecvTimeout" /app/client/callopt/streamcall/*.go 2>/dev/null | xargs echo "  Found:"

echo ""
echo "SPEC REQUIREMENT 7: Retry/fallback migration to o.UnaryOptions"
echo "  Checking WithFailureRetry uses UnaryOptions.RetryMethodPolicies:"
grep -A5 "func WithFailureRetry" /app/client/option.go 2>/dev/null | grep "UnaryOptions" >/dev/null && echo "  ✓ Migrated" || echo "  ✗ NOT migrated (still uses o.RetryMethodPolicies)"
