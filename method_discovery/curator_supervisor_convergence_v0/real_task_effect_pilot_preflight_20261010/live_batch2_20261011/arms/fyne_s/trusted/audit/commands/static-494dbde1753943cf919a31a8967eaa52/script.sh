
cd /app
echo "=== Target 5: ToolbarAction.SetIcon method ==="
grep -n "func.*ToolbarAction.*SetIcon" widget/toolbar.go
echo ""
echo "=== Target 6: Container.RemoveAll ==="
grep -n "func.*Container.*RemoveAll" container.go
echo ""
echo "=== Target 6: Hyperlink.OnTapped field ==="
grep -A 3 "type Hyperlink struct" widget/hyperlink.go | grep -E "(OnTapped|type Hyperlink)"
echo ""
echo "=== Target 6: Entry.SetMinRowsVisible ==="
grep -n "func.*Entry.*SetMinRowsVisible" widget/entry.go
echo ""
echo "=== Target 6: validation.NewAllStrings ==="
grep -n "func NewAllStrings" data/validation/*.go
