
echo "=== Target 5: Toolbar Enhancements ==="
echo "1. ToolbarAction.SetIcon() method:"
grep -n "func.*ToolbarAction.*SetIcon" /app/widget/toolbar.go

echo -e "\n2. Constructor return types (CRITICAL - must be concrete types):"
echo "   NewToolbarAction:"
grep -n "^func NewToolbarAction" /app/widget/toolbar.go

echo -e "\n   NewToolbarSpacer:"
grep -n "^func NewToolbarSpacer" /app/widget/toolbar.go

echo -e "\n   NewToolbarSeparator:"
grep -n "^func NewToolbarSeparator" /app/widget/toolbar.go

echo -e "\n=== Target 6: Widget and Container Improvements ==="
echo "1. Container.RemoveAll():"
grep -n "func.*Container.*RemoveAll" /app/container.go

echo -e "\n2. Container.Add() nil-safe check:"
grep -A 3 "^func (c \*Container) Add" /app/container.go | head -5

echo -e "\n3. Hyperlink.OnTapped field:"
grep -n "OnTapped.*func()" /app/widget/hyperlink.go

echo -e "\n4. Entry.SetMinRowsVisible():"
grep -n "func.*Entry.*SetMinRowsVisible" /app/widget/entry.go

echo -e "\n5. validation.NewAllStrings():"
ls -la /app/data/validation/all.go 2>&1
grep -n "^func NewAllStrings" /app/data/validation/all.go 2>&1

echo -e "\n=== Target 7: Desktop App Interface ==="
echo "1. driver/desktop/app.go exists:"
ls -la /app/driver/desktop/app.go 2>&1
echo -e "\n2. desktop.App interface:"
grep -A 5 "type App interface" /app/driver/desktop/app.go 2>&1
