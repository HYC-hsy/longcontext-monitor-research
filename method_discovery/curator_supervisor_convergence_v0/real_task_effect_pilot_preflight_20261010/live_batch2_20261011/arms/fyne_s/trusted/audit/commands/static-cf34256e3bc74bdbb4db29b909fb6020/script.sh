
cd /app
echo "=== Target 2: JSON Theme Functions ==="
grep -n "func FromJSON" theme/*.go
grep -n "func FromJSONReader" theme/*.go
echo ""
echo "=== Target 4: Menu Icon and Shortcut fields ==="
grep -A 5 "type MenuItem struct" menu.go | grep -E "(Icon|Shortcut|type MenuItem)"
echo ""
echo "=== Target 4: Menu Refresh methods ==="
grep -n "func.*Menu.*Refresh" menu.go
echo ""
echo "=== Target 5: Toolbar concrete return types ==="
grep -n "func NewToolbarAction" widget/toolbar.go
grep -n "func NewToolbarSpacer" widget/toolbar.go
grep -n "func NewToolbarSeparator" widget/toolbar.go
