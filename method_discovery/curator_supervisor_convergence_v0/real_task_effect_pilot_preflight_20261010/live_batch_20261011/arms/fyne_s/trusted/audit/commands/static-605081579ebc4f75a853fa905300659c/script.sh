
# Final comprehensive verification of all 7 targets
echo "=== Target 1: App.Metadata() in interface ==="
grep -n "Metadata() AppMetadata" /app/app.go

echo ""
echo "=== Target 2: parseHexColor all 4 formats ==="
grep -A 2 "switch len(hex)" /app/theme/json.go | grep "case"

echo ""
echo "=== Target 3: NewSprintf listener registration ==="
grep -A 5 "func NewSprintf" /app/data/binding/sprintf.go | grep "AddListener"

echo ""
echo "=== Target 5: Toolbar constructor return types ==="
grep "^func NewToolbar" /app/widget/toolbar.go | head -3

echo ""
echo "=== Target 6: NewAllStrings signature ==="
grep "func NewAllStrings" /app/data/validation/all.go

echo ""
echo "=== Target 7: desktop.App both methods ==="
grep -E "SetSystemTray" /app/driver/desktop/app.go | grep -v "//"

echo ""
echo "=== Build verification ==="
cd /app && go build ./... 2>&1 | head -5
echo "Exit code: $?"
