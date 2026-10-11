
# Check if Entry has MinSize or uses a renderer - look at the structure
echo "=== Entry type definition ==="
grep -A 30 "^type Entry struct" widget/entry.go | head -35
echo ""
echo "=== Searching for MinRowsVisible usage in entry rendering ==="
grep -n "MinRowsVisible" widget/entry.go
