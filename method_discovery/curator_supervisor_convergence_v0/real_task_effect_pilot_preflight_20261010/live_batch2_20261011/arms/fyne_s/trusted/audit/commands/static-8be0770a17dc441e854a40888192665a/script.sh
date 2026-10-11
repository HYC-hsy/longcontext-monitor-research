
cd /app

echo "=== Systematic Structural Verification of All 7 Targets ==="
echo
echo "Target 1 - App Metadata:"
echo "  AppMetadata struct in app.go:"
grep -A 5 "type AppMetadata struct" app.go | head -6
echo "  App.Metadata() method in interface:"
grep "Metadata()" app.go | head -1
echo
echo "Target 2 - JSON Theme:"
echo "  FromJSON and FromJSONReader functions:"
grep "^func FromJSON" theme/json_theme.go
echo
echo "Target 4 - Menu Enhancements:"
echo "  MenuItem.Icon and MenuItem.Shortcut fields:"
grep -E "(Icon|Shortcut) " menu.go | grep -v "//" | head -3
echo "  Menu.Refresh() method:"
grep "func.*Menu.*Refresh" menu.go
echo
echo "Target 5 - Toolbar Enhancements:"
echo "  ToolbarAction.SetIcon() method:"
grep "func.*SetIcon" widget/toolbar.go
echo "  Concrete return types:"
grep "func NewToolbar" widget/toolbar.go | grep -E "(Action|Spacer|Separator)"
echo
echo "Target 6 - Widget & Container:"
echo "  Container.RemoveAll():"
grep "func.*RemoveAll" container.go
echo "  Hyperlink.OnTapped field:"
grep "OnTapped" widget/hyperlink.go | grep -v "//"
echo "  Entry.SetMinRowsVisible():"
grep "func.*SetMinRowsVisible" widget/entry.go
echo "  validation.NewAllStrings():"
ls -la data/validation/all.go 2>&1 | tail -1
