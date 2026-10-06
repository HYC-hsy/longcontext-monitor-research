
# Check if Toolbar constructors were fixed
echo "=== NewToolbarSpacer ==="
grep -A2 "^func NewToolbarSpacer" /app/widget/toolbar.go

echo -e "\n=== NewToolbarSeparator ==="
grep -A2 "^func NewToolbarSeparator" /app/widget/toolbar.go

echo -e "\n=== StringToStringWithFormat ==="
grep -A5 "^func StringToStringWithFormat" /app/data/binding/sprintf.go || echo "Not found"
