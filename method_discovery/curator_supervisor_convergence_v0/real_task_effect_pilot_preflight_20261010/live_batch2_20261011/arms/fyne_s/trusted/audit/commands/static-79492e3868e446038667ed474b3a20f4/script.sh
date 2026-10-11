
# Critical: Verify Entry MinSize uses MinRowsVisible field
echo "=== Searching for MinRowsVisible usage in Entry rendering/sizing ==="
grep -n "MinRowsVisible" widget/entry.go
echo ""

# Check the entryRenderer MinSize implementation
echo "=== Entry renderer MinSize implementation ==="
awk '/type entryRenderer struct/,/^}/' widget/entry.go | head -20
echo ""

# Look for MinSize implementation in renderer
grep -A 30 "func (r \*entryRenderer) MinSize()" widget/entry.go | head -35
