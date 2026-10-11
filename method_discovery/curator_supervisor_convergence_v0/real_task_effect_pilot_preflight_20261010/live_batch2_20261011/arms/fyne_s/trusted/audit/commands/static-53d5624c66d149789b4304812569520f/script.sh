
# Check Entry.MinSize implementation more carefully for MinRowsVisible usage
echo "=== Entry renderer MinSize - checking if MinRowsVisible is used ==="
# Entry uses a renderer pattern, check the renderer
grep -n "entryRenderer\|type.*Renderer" widget/entry.go | head -5
echo ""

# Look for where MinRowsVisible would affect rendering/sizing
grep -B 3 -A 3 "MinRowsVisible" widget/entry_*.go 2>/dev/null || echo "No entry_*.go files"
echo ""

# Check if there's a separate renderer file
ls -la widget/entry*.go
echo ""

# Search for minSize in entry-related files
grep -l "minSize\|MinSize" widget/entry*.go 2>/dev/null | head -5
