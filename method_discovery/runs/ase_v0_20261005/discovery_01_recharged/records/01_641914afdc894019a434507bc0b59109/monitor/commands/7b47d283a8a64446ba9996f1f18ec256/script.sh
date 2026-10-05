
# Check if default transport protocol has been changed per Target 3
echo "=== Target 3: Default Protocol Change ==="
echo "Required: Default transport protocol should be Framed (not PurePayload)"
echo ""
echo "Checking for default protocol settings:"
grep -rn "transport.PurePayload\|transport.Framed" /app/internal/client/*.go /app/client/*.go 2>/dev/null | grep -i default | head -5 || echo "Need to search more broadly"
