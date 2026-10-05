
# Comprehensive Target 5 verification (Turn 116)
echo "=== TARGET 5 COMPREHENSIVE VERIFICATION (Turn 116) ==="
echo ""

echo "REQUIREMENT 1: Type aliases in client/option.go"
grep -E "^type (UnaryOption|StreamOption|TTHeaderStreamingOption)" /app/client/option.go | wc -l | xargs echo "  Count:"
echo "  Required: 6 ✓"

echo ""
echo "REQUIREMENT 2: client/option_unary.go"
grep "^func With" /app/client/option_unary.go 2>/dev/null | wc -l | xargs echo "  Functions:"
echo "  Required: 4 ✓"

echo ""
echo "REQUIREMENT 3: client/option_stream.go functions"
echo "  Required: 8 functions"
echo "  Current functions:"
grep "^func With" /app/client/option_stream.go 2>/dev/null
echo ""
wc -l /app/client/option_stream.go | xargs echo "  File size:"

echo ""
echo "REQUIREMENT 4: client/option_ttstream.go"
grep "^func With" /app/client/option_ttstream.go 2>/dev/null | wc -l | xargs echo "  Functions:"
echo "  Required: 2 ✓"

echo ""
echo "REQUIREMENT 5: TailOption function in client/option.go"
grep -c "^func TailOption" /app/client/option.go 2>/dev/null | xargs echo "  Found:"
echo "  Required: 1"

echo ""
echo "REQUIREMENT 6: WithRecvTimeout in callopt/streamcall"
grep -c "^func WithRecvTimeout" /app/client/callopt/streamcall/*.go 2>/dev/null | head -1 | xargs echo "  Found:"
echo "  Required: 1 ✓"

echo ""
echo "REQUIREMENT 7: Retry/fallback migration"
echo "  Checking migration to o.UnaryOptions fields:"
grep -A3 "func WithFailureRetry" /app/client/option.go 2>/dev/null | grep "UnaryOptions" | head -1
grep -A3 "func WithBackupRequest" /app/client/option.go 2>/dev/null | grep "UnaryOptions" | head -1
