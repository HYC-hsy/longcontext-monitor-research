
# Check remaining Target 5 items
echo "=== REMAINING TARGET 5 ITEMS ==="
echo ""

echo "6. WithRecvTimeout in client/callopt/streamcall:"
if [ -d "/app/client/callopt/streamcall" ]; then
  echo "   Directory exists, checking for WithRecvTimeout:"
  grep -r "WithRecvTimeout" /app/client/callopt/streamcall/ 2>/dev/null || echo "   ✗ WithRecvTimeout NOT FOUND"
else
  echo "   ✗ streamcall directory doesn't exist"
fi

echo ""
echo "7. Retry/fallback migration to UnaryOptions:"
echo "   Checking if WithFailureRetry uses o.UnaryOptions.RetryMethodPolicies:"
grep -A3 "func WithFailureRetry" /app/client/option.go 2>/dev/null | grep "UnaryOptions" || echo "   Migration check needed"
