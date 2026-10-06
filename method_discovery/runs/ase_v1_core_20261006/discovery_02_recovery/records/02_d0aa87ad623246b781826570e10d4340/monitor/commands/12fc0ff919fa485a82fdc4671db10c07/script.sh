
# Check current state of all three missing items
echo "=== 1. SetSystemTrayIcon in desktop/app.go ==="
grep "SetSystemTrayIcon" /app/driver/desktop/app.go || echo "Not found"

echo -e "\n=== 2. NewToolbarSpacer return type ==="
grep -A2 "^func NewToolbarSpacer" /app/widget/toolbar.go

echo -e "\n=== 3. NewToolbarSeparator return type ==="
grep -A2 "^func NewToolbarSeparator" /app/widget/toolbar.go

echo -e "\n=== 4. StringToStringWithFormat ==="
grep -A3 "StringToStringWithFormat" /app/data/binding/sprintf.go || echo "Not found"
