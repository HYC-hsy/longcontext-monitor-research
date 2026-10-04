
cd /app

echo "=== COMPREHENSIVE VERIFICATION OF ALL 7 TARGETS ==="
echo ""

echo "Target 1: App Metadata System"
echo "  AppMetadata struct:"
grep -A 8 "^type AppMetadata struct" app.go | head -10
echo "  App.Metadata() in interface:"
grep "Metadata() AppMetadata" app.go
echo "  SetMetadata function:"
grep "func SetMetadata" app/meta.go
echo "  Implementation count:"
grep -c "func.*Metadata.*fyne.AppMetadata" app/app.go test/testapp.go app_test.go theme/themedtestapp.go | wc -l
echo ""

echo "Target 2: JSON Theme Support"
echo "  FromJSON signature:"
grep "^func FromJSON" theme/json.go
echo "  FromJSONReader signature:"
grep "^func FromJSONReader" theme/json.go
echo "  Hex color parser:"
grep "func parseHexColor" theme/json.go
echo ""

echo "Target 3: Data Binding Formatting"
echo "  NewSprintf signature (MUST be variadic):"
grep "^func NewSprintf" data/binding/sprintf.go
echo "  StringToStringWithFormat:"
grep "^func StringToStringWithFormat" data/binding/sprintf.go
echo ""

echo "Target 4: Menu System"
echo "  MenuItem fields:"
grep -E "^\s+(Icon|Shortcut)" menu.go | head -2
echo "  Refresh methods:"
grep "^func.*Refresh" menu.go
echo ""

echo "Target 5: Toolbar"
echo "  SetIcon method:"
grep "^func.*SetIcon" widget/toolbar.go
echo "  Concrete return types:"
grep "^func NewToolbar" widget/toolbar.go | grep -E "\*Toolbar(Action|Spacer|Separator)"
echo ""

echo "Target 6: Container & Widgets"
echo "  Container.RemoveAll:"
grep "^func.*RemoveAll" container.go
echo "  Hyperlink.OnTapped:"
grep "OnTapped.*func()" widget/hyperlink.go | head -1
echo "  Entry.SetMinRowsVisible:"
grep "^func.*SetMinRowsVisible" widget/entry.go
echo "  NewAllStrings validator:"
grep "^func NewAllStrings" data/validation/all.go
echo ""

echo "Target 7: Desktop App Interface"
echo "  desktop.App methods:"
grep -A 1 "SetSystemTray" driver/desktop/app.go
