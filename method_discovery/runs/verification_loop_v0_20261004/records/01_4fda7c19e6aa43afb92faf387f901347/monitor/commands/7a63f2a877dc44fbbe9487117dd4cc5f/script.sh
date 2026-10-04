
# Verify Targets 5-7
cd /app

echo "=== TARGET 5: Toolbar Enhancements ==="
echo "1. ToolbarAction.SetIcon method:"
grep -A 3 "func.*SetIcon" widget/toolbar.go

echo -e "\n2. Constructor return types (must be concrete, not ToolbarItem):"
grep "^func NewToolbarAction" widget/toolbar.go
grep "^func NewToolbarSpacer" widget/toolbar.go
grep "^func NewToolbarSeparator" widget/toolbar.go

echo -e "\n=== TARGET 6: Widget and Container Improvements ==="
echo "1. Container.RemoveAll():"
grep -A 3 "func.*RemoveAll" container.go

echo -e "\n2. Container.Add() nil-safe:"
grep -B 2 -A 2 "if o == nil" container.go

echo -e "\n3. Hyperlink.OnTapped field:"
grep "OnTapped" widget/hyperlink.go | head -3

echo -e "\n4. Entry.SetMinRowsVisible method:"
grep -A 3 "func.*SetMinRowsVisible" widget/entry.go

echo -e "\n5. validation.NewAllStrings in data/validation/all.go:"
ls -la data/validation/all.go && grep "^func NewAllStrings" data/validation/all.go

echo -e "\n=== TARGET 7: Desktop App Interface ==="
echo "1. driver/desktop/app.go exists:"
ls -la driver/desktop/app.go && cat driver/desktop/app.go
