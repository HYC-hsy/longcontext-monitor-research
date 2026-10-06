
# Verify all 7 targets are present
echo "=== Checking all 7 targets ==="
echo "Target 1: AppMetadata struct and Metadata() in App interface"
grep -q "type AppMetadata struct" /app/app.go && echo "✓ AppMetadata struct exists"
grep -q "Metadata() AppMetadata" /app/app.go && echo "✓ Metadata() in App interface"
grep -q "func SetMetadata" /app/app/meta.go && echo "✓ SetMetadata function exists"

echo ""
echo "Target 2: JSON Theme Support"
test -f /app/theme/json.go && echo "✓ theme/json.go exists"

echo ""
echo "Target 3: Data Binding Formatting"
test -f /app/data/binding/sprintf.go && echo "✓ data/binding/sprintf.go exists"

echo ""
echo "Target 4: Menu System Enhancements"
grep -q "Icon Resource" /app/menu.go && echo "✓ MenuItem.Icon field exists"
grep -q "Shortcut Shortcut" /app/menu.go && echo "✓ MenuItem.Shortcut field exists"

echo ""
echo "Target 5: Toolbar Enhancements"
grep -q "func.*SetIcon" /app/widget/toolbar.go && echo "✓ ToolbarAction.SetIcon exists"

echo ""
echo "Target 6: Widget and Container Improvements"
grep -q "func.*RemoveAll" /app/container.go && echo "✓ Container.RemoveAll exists"
grep -q "OnTapped func()" /app/widget/hyperlink.go && echo "✓ Hyperlink.OnTapped exists"
grep -q "func.*SetMinRowsVisible" /app/widget/entry.go && echo "✓ Entry.SetMinRowsVisible exists"
test -f /app/data/validation/all.go && echo "✓ validation.NewAllStrings exists"

echo ""
echo "Target 7: Desktop App Interface"
test -f /app/driver/desktop/app.go && echo "✓ driver/desktop/app.go exists"
grep -q "SetSystemTrayMenu" /app/driver/desktop/app.go && echo "✓ SetSystemTrayMenu method"
grep -q "SetSystemTrayIcon" /app/driver/desktop/app.go && echo "✓ SetSystemTrayIcon method"
