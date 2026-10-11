
# Verify Target 5: Check toolbar constructor return types
echo "=== Target 5: Toolbar constructor signatures ==="
grep -n "func NewToolbarAction" /app/widget/toolbar.go
grep -n "func NewToolbarSpacer" /app/widget/toolbar.go
grep -n "func NewToolbarSeparator" /app/widget/toolbar.go
