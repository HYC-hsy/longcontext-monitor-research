
# Check Target 5: Verify toolbar constructor return types (must be concrete, not interface)
cd /app
grep -A2 "^func NewToolbarAction\|^func NewToolbarSpacer\|^func NewToolbarSeparator" widget/toolbar.go
