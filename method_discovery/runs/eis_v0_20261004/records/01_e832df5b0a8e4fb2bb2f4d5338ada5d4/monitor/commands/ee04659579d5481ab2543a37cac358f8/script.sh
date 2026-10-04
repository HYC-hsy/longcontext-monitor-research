
# Final comprehensive verification of all 7 targets
echo "=== VERIFICATION OF ALL 7 TARGETS ==="

echo -e "\n=== T1: AppMetadata struct fields ==="
grep -A10 "type AppMetadata struct" /app/app.go | head -15

echo -e "\n=== T1: SetMetadata function location ==="
ls -la /app/internal/app/meta.go 2>&1 | head -1

echo -e "\n=== T2: JSON theme functions ==="
grep -E "^func (FromJSON|FromJSONReader)" /app/theme/json.go

echo -e "\n=== T3: Data binding functions ==="
grep -E "^func (NewSprintf|StringToStringWithFormat)" /app/data/binding/sprintf.go

echo -e "\n=== T4: MenuItem fields ==="
grep -A15 "type MenuItem struct" /app/menu.go | grep -E "(Icon|Shortcut)"

echo -e "\n=== T4: Menu Refresh methods ==="
grep -E "^func \(m \*.*Menu\) Refresh" /app/menu.go

echo -e "\n=== T5: Toolbar return types ==="
grep -E "^func NewToolbar(Action|Spacer|Separator)" /app/widget/toolbar.go

echo -e "\n=== T5: SetIcon method ==="
grep -A2 "^func (t \*ToolbarAction) SetIcon" /app/widget/toolbar.go

echo -e "\n=== T6: Container methods ==="
grep -E "^func \(c \*Container\) (RemoveAll|Add)" /app/container.go

echo -e "\n=== T6: Hyperlink.OnTapped ==="
grep -B2 "OnTapped.*func()" /app/widget/hyperlink.go | head -4

echo -e "\n=== T6: Entry.SetMinRowsVisible ==="
grep -A2 "^func (e \*Entry) SetMinRowsVisible" /app/widget/entry.go

echo -e "\n=== T6: NewAllStrings validator ==="
grep -A2 "^func NewAllStrings" /app/data/validation/all.go

echo -e "\n=== T7: desktop.App both required methods ==="
grep -E "SetSystemTray(Menu|Icon)" /app/driver/desktop/app.go

echo -e "\n=== BUILD STATUS ==="
cd /app && go build ./... 2>&1 && echo "BUILD: SUCCESS" || echo "BUILD: FAILED"
