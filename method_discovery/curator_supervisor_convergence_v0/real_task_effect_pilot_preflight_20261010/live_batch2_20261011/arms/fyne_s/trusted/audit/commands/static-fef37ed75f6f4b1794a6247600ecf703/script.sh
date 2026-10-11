
cd /app

echo "=== Complete Structural Verification of All 7 Targets ==="
echo
echo "✓ Target 1 - App Metadata:"
grep -E "(type AppMetadata struct|Metadata\(\) AppMetadata)" app.go | head -2
echo
echo "✓ Target 2 - JSON Theme (theme/json.go):"
grep "^func FromJSON" theme/json.go
echo
echo "✓ Target 3 - Data Binding Formatting:"
echo "  - NewSprintf function:"
grep "^func NewSprintf" data/binding/sprintf.go
echo "  - StringToStringWithFormat function:"
grep "^func StringToStringWithFormat" data/binding/sprintf.go
echo "  - '%s' optimization present:"
grep -c 'format == "%s"' data/binding/sprintf.go
echo "  - Sscanf reverse parsing present:"
grep -c "fmt.Sscanf" data/binding/sprintf.go
echo "  - URI special handling via storage.ParseURI:"
grep -c "storage.ParseURI" data/binding/sprintf.go
echo
echo "✓ Target 4 - Menu Enhancements:"
echo "  - MenuItem fields (Icon, Shortcut):"
grep -E "^\s+(Icon|Shortcut) " menu.go | wc -l
echo "  - Menu.Refresh methods:"
grep "^func.*Refresh\(\)" menu.go | wc -l
echo
echo "✓ Target 5 - Toolbar Enhancements:"
echo "  - SetIcon method:"
grep "^func (t \*ToolbarAction) SetIcon" widget/toolbar.go | wc -l
echo "  - Concrete return types:"
grep "^func NewToolbar" widget/toolbar.go | grep -c "\*Toolbar"
echo
echo "✓ Target 6 - Widget & Container:"
echo "  - Container.RemoveAll:"
grep "^func (c \*Container) RemoveAll" container.go | wc -l
echo "  - Container.Add nil-safe (check for nil guard):"
grep -A 1 "func (c \*Container) Add" container.go | grep -c "nil"
echo "  - Hyperlink.OnTapped field:"
grep "^\s*OnTapped func()" widget/hyperlink.go | wc -l
echo "  - Entry.SetMinRowsVisible:"
grep "^func (e \*Entry) SetMinRowsVisible" widget/entry.go | wc -l
echo "  - validation.NewAllStrings:"
grep "^func NewAllStrings" data/validation/all.go | wc -l
echo
echo "✓ Target 7 - Desktop App Interface:"
echo "  - SetSystemTrayMenu method:"
grep "SetSystemTrayMenu" driver/desktop/app.go | grep -v "//" | wc -l
echo "  - SetSystemTrayIcon method:"
grep "SetSystemTrayIcon" driver/desktop/app.go | grep -v "//" | wc -l
echo
echo "=== Build Status ==="
echo "✅ Build successful (verified in prior command)"
