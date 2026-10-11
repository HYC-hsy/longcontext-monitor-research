
# Verify key structural elements exist and are importable
cd /app

echo "=== Verifying Target 1: App.Metadata() method ==="
grep -n "Metadata()" app.go | head -3

echo ""
echo "=== Verifying Target 2: JSON theme functions ==="
ls -la theme/json.go 2>/dev/null && echo "✓ theme/json.go exists" || echo "✗ theme/json.go missing"

echo ""
echo "=== Verifying Target 4: Menu Refresh methods ==="
grep -n "func.*Refresh()" menu.go

echo ""
echo "=== Verifying Target 5: Toolbar concrete returns ==="
grep -n "func NewToolbar" widget/toolbar.go | head -5

echo ""
echo "=== Verifying Target 6: Container.RemoveAll ==="
grep -n "func.*RemoveAll" container.go

echo ""
echo "=== Verifying Target 6: Entry.SetMinRowsVisible ==="
grep -n "SetMinRowsVisible" widget/entry.go

echo ""
echo "=== Verifying Target 6: Hyperlink.OnTapped field ==="
grep -n "OnTapped" widget/hyperlink.go | head -2

echo ""
echo "=== Verifying Target 6: validation.NewAllStrings ==="
ls -la data/validation/all.go 2>/dev/null && echo "✓ data/validation/all.go exists" || echo "✗ missing"
