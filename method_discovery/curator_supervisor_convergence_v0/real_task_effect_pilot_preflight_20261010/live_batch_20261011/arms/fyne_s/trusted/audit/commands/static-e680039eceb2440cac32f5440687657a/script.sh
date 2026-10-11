
# Get exact function signatures with return types
echo "=== Exact toolbar constructor signatures ==="
grep -A 3 "^func NewToolbarAction" /app/widget/toolbar.go | head -5
echo ""
grep -A 3 "^func NewToolbarSpacer" /app/widget/toolbar.go | head -5
echo ""
grep -A 3 "^func NewToolbarSeparator" /app/widget/toolbar.go | head -5
