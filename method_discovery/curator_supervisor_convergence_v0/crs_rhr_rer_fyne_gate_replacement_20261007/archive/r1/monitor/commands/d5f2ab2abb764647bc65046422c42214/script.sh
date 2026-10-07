
# Final comprehensive verification of all 7 targets
echo "=== TARGET 1: App Metadata ==="
grep -n "type AppMetadata struct" /app/app.go
grep -n "Metadata() AppMetadata" /app/app.go
ls /app/app/meta.go 2>/dev/null && echo "meta.go exists" || echo "MISSING"

echo -e "\n=== TARGET 2: JSON Theme ==="
grep -n "func FromJSON" /app/theme/json.go | head -1
grep -n "func FromJSONReader" /app/theme/json.go | head -1

echo -e "\n=== TARGET 3: Data Binding ==="
grep -n "func NewSprintf" /app/data/binding/sprintf.go | head -1
grep -n "func StringToStringWithFormat" /app/data/binding/sprintf.go | head -1

echo -e "\n=== TARGET 4: Menu Enhancements ==="
grep -n "Icon Resource" /app/menu.go | head -1
grep -n "Shortcut Shortcut" /app/menu.go | head -1
grep -n "func.*Refresh" /app/menu.go

echo -e "\n=== TARGET 5: Toolbar ==="
grep -n "func.*SetIcon" /app/widget/toolbar.go | head -1
grep -n "func NewToolbarAction.*\*ToolbarAction" /app/widget/toolbar.go

echo -e "\n=== TARGET 6: Widget/Container ==="
grep -n "func.*RemoveAll" /app/container.go | head -1
grep -n "func NewAllStrings" /app/validation.go | head -1

echo -e "\n=== TARGET 7: Desktop App ==="
grep -n "SetSystemTrayMenu\|SetSystemTrayIcon" /app/driver/desktop/app.go
