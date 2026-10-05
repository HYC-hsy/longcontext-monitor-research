
# Check current state of toolbar.go return types
echo "=== Current NewToolbarSpacer return type ==="
grep -A 1 "^func NewToolbarSpacer" /app/widget/toolbar.go

echo -e "\n=== Current NewToolbarSeparator return type ==="
grep -A 1 "^func NewToolbarSeparator" /app/widget/toolbar.go
