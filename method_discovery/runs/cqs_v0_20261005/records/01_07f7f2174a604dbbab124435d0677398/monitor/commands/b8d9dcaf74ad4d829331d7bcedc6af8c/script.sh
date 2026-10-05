
# Check toolbar.go for the required changes
echo "=== Checking SetIcon method ==="
grep -n "func (t \*ToolbarAction) SetIcon" /app/widget/toolbar.go

echo -e "\n=== Checking NewToolbarAction return type ==="
grep -n "^func NewToolbarAction" /app/widget/toolbar.go

echo -e "\n=== Checking NewToolbarSpacer return type ==="
grep -n "^func NewToolbarSpacer" /app/widget/toolbar.go

echo -e "\n=== Checking NewToolbarSeparator return type ==="
grep -n "^func NewToolbarSeparator" /app/widget/toolbar.go
