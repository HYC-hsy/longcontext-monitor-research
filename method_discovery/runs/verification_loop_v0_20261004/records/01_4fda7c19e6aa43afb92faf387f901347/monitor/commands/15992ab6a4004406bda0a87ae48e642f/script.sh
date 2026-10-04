
# Final verification: Check all 7 targets are in place
cd /app

echo "=== Target 1: App Metadata ==="
grep -n "type AppMetadata struct" app.go | head -1
grep -n "Metadata() AppMetadata" app.go | head -1
ls -la app/meta.go 2>&1 | grep -q "meta.go" && echo "✓ app/meta.go exists" || echo "✗ MISSING"

echo ""
echo "=== Target 2: JSON Theme ==="
ls -la theme/json.go 2>&1 | grep -q "json.go" && echo "✓ theme/json.go exists" || echo "✗ MISSING"

echo ""
echo "=== Target 3: Data Binding ==="
ls -la data/binding/sprintf.go 2>&1 | grep -q "sprintf.go" && echo "✓ data/binding/sprintf.go exists" || echo "✗ MISSING"

echo ""
echo "=== Target 4: Menu Enhancements ==="
grep -n "Icon.*Resource" menu.go | grep MenuItem | head -1
grep -n "Shortcut.*Shortcut" menu.go | grep MenuItem | head -1
grep -n "func.*Refresh()" menu.go | head -2

echo ""
echo "=== Target 5: Toolbar ==="
grep -n "SetIcon" widget/toolbar.go | head -1
grep "func NewToolbarAction" widget/toolbar.go | head -1
grep "func NewToolbarSpacer" widget/toolbar.go | head -1
grep "func NewToolbarSeparator" widget/toolbar.go | head -1
