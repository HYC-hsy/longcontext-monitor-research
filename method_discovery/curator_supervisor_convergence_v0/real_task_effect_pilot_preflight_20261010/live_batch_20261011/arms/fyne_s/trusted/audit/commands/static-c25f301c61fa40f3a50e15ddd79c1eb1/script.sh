
# Verify all three targets are now correct

echo "=== Target 7: desktop.App (should have 2 methods) ==="
grep -A 12 "type App interface" /app/driver/desktop/app.go | head -15

echo ""
echo "=== Target 6: NewAllStrings (should accept ...fyne.StringValidator) ==="
grep -B 3 -A 8 "func NewAllStrings" /app/data/validation/all.go

echo ""
echo "=== Target 2: JSON Theme struct (should have Sizes, Fonts, Icons) ==="
grep -A 30 "type jsonTheme struct" /app/theme/json.go | head -35
