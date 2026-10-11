
# Final verification: check that all 7 targets meet requirements
echo "=== Target 1: App.Metadata() interface method ==="
grep -n "Metadata() AppMetadata" /app/app.go

echo ""
echo "=== Target 2: JSON theme sections parsed to correct maps ==="
grep -A 8 "Parse colors (generic)" /app/theme/json.go | head -10
grep -A 8 "Parse colors-dark" /app/theme/json.go | head -10

echo ""
echo "=== Target 5: Toolbar constructors return concrete types ==="
grep "^func NewToolbarAction" /app/widget/toolbar.go
grep "^func NewToolbarSpacer" /app/widget/toolbar.go
grep "^func NewToolbarSeparator" /app/widget/toolbar.go

echo ""
echo "=== Target 6: NewAllStrings signature ==="
grep "func NewAllStrings" /app/data/validation/all.go

echo ""
echo "=== Target 7: desktop.App methods ==="
grep -A 2 "SetSystemTrayMenu\|SetSystemTrayIcon" /app/driver/desktop/app.go | head -8
