
# Verify that all key APIs are importable by checking actual implementation files exist
echo "=== Structural Verification ==="
echo "Target 1 - App Metadata:"
grep -n "type AppMetadata struct" /app/app.go | head -1
grep -n "Metadata() AppMetadata" /app/app.go | head -1
grep -n "func SetMetadata" /app/app/meta.go | head -1

echo -e "\nTarget 2 - JSON Theme:"
grep -n "func FromJSON" /app/theme/json.go | head -1
grep -n "func FromJSONReader" /app/theme/json.go | head -1

echo -e "\nTarget 3 - Sprintf Binding:"
grep -n "func NewSprintf" /app/data/binding/sprintf.go | head -1
grep -n "func StringToStringWithFormat" /app/data/binding/sprintf.go | head -1

echo -e "\nTarget 4 - Menu Enhancements:"
grep -n "Icon Resource" /app/menu.go | head -1
grep -n "Shortcut Shortcut" /app/menu.go | head -1
grep -n "func (m \*Menu) Refresh" /app/menu.go | head -1
grep -n "func (m \*MainMenu) Refresh" /app/menu.go | head -1

echo -e "\nTarget 5 - Toolbar:"
grep -n "func NewToolbarAction.*\*ToolbarAction" /app/widget/toolbar.go | head -1

echo -e "\nTarget 6 - Widget Improvements:"
grep -n "func (c \*Container) RemoveAll" /app/container.go | head -1
grep -n "func (e \*Entry) SetMinRowsVisible" /app/widget/entry.go | head -1
grep -n "OnTapped func()" /app/widget/hyperlink.go | head -1
grep -n "func NewAllStrings" /app/data/validation/all.go | head -1

echo -e "\nTarget 7 - Desktop App:"
grep -n "SetSystemTrayMenu" /app/driver/desktop/app.go | head -1
grep -n "SetSystemTrayIcon" /app/driver/desktop/app.go | head -1
