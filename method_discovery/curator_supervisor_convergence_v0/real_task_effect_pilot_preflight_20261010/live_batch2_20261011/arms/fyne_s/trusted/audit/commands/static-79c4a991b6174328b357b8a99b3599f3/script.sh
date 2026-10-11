
# Verify all remaining structural targets systematically
echo "=== Target 4: Menu.Refresh and MainMenu.Refresh methods ==="
grep -A 3 "func (m \*Menu) Refresh" menu.go
grep -A 3 "func (m \*MainMenu) Refresh" menu.go
echo ""

echo "=== Target 5: Toolbar concrete return types ==="
grep "^func NewToolbarAction" widget/toolbar.go
grep "^func NewToolbarSpacer" widget/toolbar.go
grep "^func NewToolbarSeparator" widget/toolbar.go
echo ""

echo "=== Target 5: ToolbarAction.SetIcon method ==="
grep -A 5 "func (t \*ToolbarAction) SetIcon" widget/toolbar.go
echo ""

echo "=== Target 6: Container.RemoveAll ==="
grep -A 5 "func (c \*Container) RemoveAll" container.go
echo ""

echo "=== Target 6: Hyperlink.OnTapped field ==="
grep -A 3 "OnTapped func()" widget/hyperlink.go
echo ""

echo "=== Target 6: Entry.SetMinRowsVisible and MinRowsVisible field ==="
grep "MinRowsVisible int" widget/entry.go
grep -A 5 "func (e \*Entry) SetMinRowsVisible" widget/entry.go
echo ""

echo "=== Target 6: validation.NewAllStrings ==="
grep -A 8 "func NewAllStrings" data/validation/all.go
