
cd /app
echo "=== Systematic Verification of All 7 Targets ==="
echo ""
echo "Target 1: App Metadata"
echo "  - AppMetadata struct:" && grep -n "^type AppMetadata struct" app.go
echo "  - App.Metadata method:" && grep -n "Metadata() AppMetadata" app.go
echo "  - SetMetadata function:" && grep -n "^func SetMetadata" app/meta.go
echo ""
echo "Target 2: JSON Theme"
echo "  - FromJSON:" && grep -n "^func FromJSON" theme/json.go
echo "  - FromJSONReader:" && grep -n "^func FromJSONReader" theme/json.go
echo ""
echo "Target 3: Data Binding (behavioral verified in prior focal CRS)"
echo "  - NewSprintf:" && grep -n "^func NewSprintf" data/binding/sprintf.go
echo "  - StringToStringWithFormat:" && grep -n "^func StringToStringWithFormat" data/binding/sprintf.go
echo ""
echo "Target 4: Menu Enhancements"
echo "  - MenuItem.Icon field:" && grep -n "Icon Resource" menu.go | head -1
echo "  - MenuItem.Shortcut field:" && grep -n "Shortcut Shortcut" menu.go
echo "  - Menu.Refresh:" && grep -n "^func (m \*Menu) Refresh" menu.go
echo "  - MainMenu.Refresh:" && grep -n "^func (m \*MainMenu) Refresh" menu.go
echo ""
echo "Target 5: Toolbar"
echo "  - SetIcon method:" && grep -n "^func (t \*ToolbarAction) SetIcon" widget/toolbar.go
echo "  - NewToolbarAction signature:" && grep -n "^func NewToolbarAction" widget/toolbar.go
echo "  - NewToolbarSpacer signature:" && grep -n "^func NewToolbarSpacer" widget/toolbar.go
echo "  - NewToolbarSeparator signature:" && grep -n "^func NewToolbarSeparator" widget/toolbar.go
echo ""
echo "Target 6: Widget & Container"
echo "  - Container.RemoveAll:" && grep -n "^func (c \*Container) RemoveAll" container.go
echo "  - Container.Add nil-safe:" && grep -A 2 "^func (c \*Container) Add" container.go | grep "if add == nil"
echo "  - Hyperlink.OnTapped:" && grep -n "OnTapped func()" widget/hyperlink.go
echo "  - Entry.SetMinRowsVisible:" && grep -n "^func (e \*Entry) SetMinRowsVisible" widget/entry.go
echo "  - NewAllStrings:" && grep -n "^func NewAllStrings" data/validation/all.go
echo ""
echo "Target 7: Desktop App"
echo "  - desktop.App interface:" && grep -n "^type App interface" driver/desktop/app.go
echo "  - SetSystemTrayMenu:" && grep -n "SetSystemTrayMenu" driver/desktop/app.go | head -1
echo "  - SetSystemTrayIcon:" && grep -n "SetSystemTrayIcon" driver/desktop/app.go | head -1
