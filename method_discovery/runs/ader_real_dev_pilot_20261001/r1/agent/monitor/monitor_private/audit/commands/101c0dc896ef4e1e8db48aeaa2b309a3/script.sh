
# Check if any of the target files exist
cd /app
echo "=== Checking Target 1: app/meta.go ==="
test -f app/meta.go && echo "EXISTS" || echo "NOT FOUND"

echo "=== Checking Target 2: theme JSON support ==="
grep -r "FromJSON" theme/ 2>/dev/null | head -5 || echo "NOT FOUND"

echo "=== Checking Target 3: binding/sprintf.go ==="
test -f data/binding/sprintf.go && echo "EXISTS" || echo "NOT FOUND"

echo "=== Checking Target 5: ToolbarAction.SetIcon ==="
grep -n "SetIcon" widget/toolbar.go 2>/dev/null | head -3 || echo "NOT FOUND"

echo "=== Checking Target 6: Container.RemoveAll ==="
grep -n "RemoveAll" container.go 2>/dev/null | head -3 || echo "NOT FOUND"

echo "=== Checking Target 7: driver/desktop/app.go ==="
test -f driver/desktop/app.go && echo "EXISTS" || echo "NOT FOUND"
