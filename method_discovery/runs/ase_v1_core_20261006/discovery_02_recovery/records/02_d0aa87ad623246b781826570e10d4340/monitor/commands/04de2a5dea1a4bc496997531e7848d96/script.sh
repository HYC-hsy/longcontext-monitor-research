
# Check Target 5: Toolbar constructor return types
grep -A2 "^func NewToolbarAction" /app/widget/toolbar.go
echo "---"
grep -A2 "^func NewToolbarSpacer" /app/widget/toolbar.go
echo "---"
grep -A2 "^func NewToolbarSeparator" /app/widget/toolbar.go
