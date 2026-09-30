
# Check current state after turn 51 (cursor 102)
echo "=== Entry widget ==="
grep -n "SetMinRowsVisible" /app/widget/entry.go 2>&1 || echo "SetMinRowsVisible not found in entry.go"
grep -n "minRowsVisible" /app/widget/entry.go 2>&1 || echo "minRowsVisible field not found in entry.go"

echo ""
echo "=== Select widget ==="
grep -n "SetMinRowsVisible" /app/widget/select.go 2>&1 || echo "SetMinRowsVisible not found in select.go (GOOD)"
grep -n "MinRowsVisible" /app/widget/select.go 2>&1 || echo "MinRowsVisible field not found in select.go (GOOD)"
