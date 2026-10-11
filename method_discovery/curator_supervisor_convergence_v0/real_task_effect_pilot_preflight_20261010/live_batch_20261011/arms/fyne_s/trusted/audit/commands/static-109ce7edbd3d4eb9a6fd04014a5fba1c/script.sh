
# Verify Target 5 fix: check current toolbar constructor signatures
echo "=== Current toolbar constructor return types ==="
grep -n "^func NewToolbarAction" /app/widget/toolbar.go
grep -n "^func NewToolbarSpacer" /app/widget/toolbar.go
grep -n "^func NewToolbarSeparator" /app/widget/toolbar.go

echo ""
echo "=== Build verification ==="
cd /app && go build ./... 2>&1 | head -20
echo "Exit code: $?"
