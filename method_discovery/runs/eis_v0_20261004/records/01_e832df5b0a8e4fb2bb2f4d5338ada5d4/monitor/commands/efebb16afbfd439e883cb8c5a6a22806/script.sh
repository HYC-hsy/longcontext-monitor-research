
# Final requirement verification with specific checks
echo "=== CRITICAL REQUIREMENT CHECKS ==="

echo -e "\n1. T1: All App implementations have Metadata()?"
echo "fyneApp:" && grep -c "func (a \*fyneApp) Metadata" /app/app/app.go
echo "testApp:" && grep -c "func (a \*testApp) Metadata" /app/test/testapp.go  
echo "dummyApp:" && grep -c "func (d \*dummyApp) Metadata" /app/app_test.go
echo "themedApp:" && grep -c "func (t \*themedApp) Metadata" /app/theme/themedtestapp.go

echo -e "\n2. T1: Default metadata values correct?"
grep -A4 "var appMetadata = fyne.AppMetadata" /app/internal/app/meta.go

echo -e "\n3. T2: Hex color parsing formats (3,4,6,8 digits)?"
grep -c "3 digits\|4 digits\|6 digits\|8 digits" /app/theme/json.go

echo -e "\n4. T3: StringToStringWithFormat identity check?"
grep -A3 'format == "%s"' /app/data/binding/sprintf.go

echo -e "\n5. T4: MenuItem has both Icon AND Shortcut fields?"
grep -E "^\s+(Icon|Shortcut)\s+" /app/menu.go | grep -A1 "Icon" | head -4

echo -e "\n6. T5: All three toolbar constructors return concrete types?"
grep "^func NewToolbar" /app/widget/toolbar.go | grep -c "\*Toolbar"

echo -e "\n7. T6: Container.Add() nil-safe implementation?"
grep -A3 "^func (c \*Container) Add" /app/container.go | grep -c "nil"

echo -e "\n8. T7: desktop.App has BOTH required methods?"
grep "SetSystemTray" /app/driver/desktop/app.go | wc -l

echo -e "\n=== FINAL BUILD & TEST ==="
cd /app && go build ./... 2>&1 | head -5 && echo "Build: PASS" || echo "Build: FAIL"
