
echo "=== Target 5: Toolbar Return Types ==="
grep -n "^func NewToolbarSpacer" /app/widget/toolbar.go
grep -n "^func NewToolbarSeparator" /app/widget/toolbar.go

echo -e "\n=== Target 7: Desktop App Interface ==="
grep -n "^type App interface" /app/driver/desktop/app.go
grep -n "SetSystemTray" /app/driver/desktop/app.go
