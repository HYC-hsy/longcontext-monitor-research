
# Verify critical elements across all 7 targets
echo "=== Target 5: Toolbar constructor return types ==="
grep -A 2 "^func NewToolbarAction" /app/widget/toolbar.go
grep -A 2 "^func NewToolbarSpacer" /app/widget/toolbar.go  
grep -A 2 "^func NewToolbarSeparator" /app/widget/toolbar.go

echo ""
echo "=== Target 6: Widget improvements ==="
echo "Container.RemoveAll:"
grep -A 5 "func (c \*Container) RemoveAll" /app/container.go

echo ""
echo "Hyperlink.OnTapped:"
grep "OnTapped" /app/widget/hyperlink.go | head -5

echo ""
echo "Entry.SetMinRowsVisible:"
grep -A 3 "func (e \*Entry) SetMinRowsVisible" /app/widget/entry.go

echo ""
echo "validation.NewAllStrings:"
grep -A 5 "func NewAllStrings" /app/data/validation/all.go
