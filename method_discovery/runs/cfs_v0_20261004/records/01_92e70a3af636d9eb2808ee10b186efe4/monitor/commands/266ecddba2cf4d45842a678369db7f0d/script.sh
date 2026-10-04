
# Verify all 7 targets with specific checks
cd /app

echo "=== Target 1: App Metadata ==="
grep -n "type AppMetadata struct" app.go | head -2
grep -n "Metadata() AppMetadata" app.go | head -2
grep -n "func (a \*fyneApp) Metadata" app/app.go | head -1
grep -n "func (a \*testApp) Metadata" test/testapp.go | head -1
grep -n "func SetMetadata" app/meta.go | head -1

echo -e "\n=== Target 2: JSON Theme ==="
grep -n "func FromJSON" theme/json.go | head -2
grep -n "func FromJSONReader" theme/json.go | head -1
grep -n "parseHexColor" theme/json.go | head -1

echo -e "\n=== Target 3: Data Binding ==="
grep -n "func NewSprintf" data/binding/sprintf.go | head -1
grep -n "func StringToStringWithFormat" data/binding/sprintf.go | head -1

echo -e "\n=== Target 4: Menu Enhancements ==="
grep -n "Icon.*Resource" menu.go | head -1
grep -n "Shortcut.*Shortcut" menu.go | head -1
grep -n "func (m \*Menu) Refresh" menu.go | head -1
grep -n "func (m \*MainMenu) Refresh" menu.go | head -1

echo -e "\n=== Target 5: Toolbar ==="
grep -n "func (t \*ToolbarAction) SetIcon" widget/toolbar.go | head -1
grep -n "func NewToolbarAction.*\*ToolbarAction" widget/toolbar.go | head -1

echo -e "\n=== Target 6: Widget/Container ==="
grep -n "func (c \*Container) RemoveAll" container.go | head -1
grep -n "OnTapped.*func()" widget/hyperlink.go | head -1
grep -n "func (e \*Entry) SetMinRowsVisible" widget/entry.go | head -1
grep -n "func NewAllStrings" data/validation/all.go | head -1

echo -e "\n=== Target 7: Desktop App ==="
grep -n "SetSystemTrayMenu" driver/desktop/app.go
grep -n "SetSystemTrayIcon" driver/desktop/app.go
