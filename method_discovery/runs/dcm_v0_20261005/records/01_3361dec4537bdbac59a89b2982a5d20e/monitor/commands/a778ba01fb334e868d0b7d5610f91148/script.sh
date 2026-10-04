
# Comprehensive final verification
cd /app

echo "=== FINAL VERIFICATION OF ALL 7 TARGETS ==="
echo ""

echo "Target 1 - App.Metadata() in both implementations:"
grep -n "func.*Metadata().*AppMetadata" app/app.go test/testapp.go | head -5

echo ""
echo "Target 2 - JSON Theme functions:"
grep -n "^func FromJSON\|^func FromJSONReader" theme/json.go

echo ""
echo "Target 3 - Data binding formatting:"
grep -n "^func NewSprintf\|^func StringToStringWithFormat" data/binding/sprintf.go

echo ""
echo "Target 4 - Menu Icon/Shortcut fields:"
grep -n "Icon.*Resource\|Shortcut.*Shortcut" menu.go | grep -A1 "type MenuItem"

echo ""
echo "Target 5 - Toolbar return types (must be concrete):"
grep -n "^func NewToolbarAction\|^func NewToolbarSpacer\|^func NewToolbarSeparator" widget/toolbar.go | head -3

echo ""
echo "Target 6 - Widget improvements:"
echo "  - Container.RemoveAll:"
grep -n "^func (c \*Container) RemoveAll" container.go
echo "  - Hyperlink.OnTapped:"
grep -n "OnTapped.*func()" widget/hyperlink.go | head -1
echo "  - Entry.SetMinRowsVisible:"
grep -n "^func (e \*Entry) SetMinRowsVisible" widget/entry.go
echo "  - NewAllStrings signature:"
grep -n "^func NewAllStrings" data/validation/allstrings.go

echo ""
echo "Target 7 - desktop.App interface methods:"
grep -n "SetSystemTrayMenu\|SetSystemTrayIcon" driver/desktop/app.go | head -4
