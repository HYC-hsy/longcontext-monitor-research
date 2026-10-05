
# Verify the toolbar.go corrections
echo "=== Checking NewToolbarSpacer return type after correction ==="
grep -n "^func NewToolbarSpacer" /app/widget/toolbar.go

echo -e "\n=== Checking NewToolbarSeparator return type after correction ==="
grep -n "^func NewToolbarSeparator" /app/widget/toolbar.go
