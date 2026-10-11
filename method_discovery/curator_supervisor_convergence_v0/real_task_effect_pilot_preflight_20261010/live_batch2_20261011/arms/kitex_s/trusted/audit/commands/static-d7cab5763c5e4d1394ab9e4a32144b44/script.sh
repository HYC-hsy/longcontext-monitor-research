
# Check if TailOption was added to option.go
echo "=== Checking for TailOption in option.go ==="
grep -n "TailOption" /app/client/option.go | head -5
echo ""
# Check if WithRecvTimeout was added to streamcall
echo "=== Checking for WithRecvTimeout in streamcall ==="
grep -n "WithRecvTimeout" /app/client/callopt/streamcall/*.go 2>/dev/null | head -5
