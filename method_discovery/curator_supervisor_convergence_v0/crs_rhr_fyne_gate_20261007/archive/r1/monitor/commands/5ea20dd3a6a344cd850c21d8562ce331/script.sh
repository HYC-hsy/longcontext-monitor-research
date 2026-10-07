
# Verify all Target 6 files exist with correct names
echo "=== Checking Target 6 implementations ==="
echo "Container.RemoveAll:"
grep -n "func.*RemoveAll" /app/container.go
echo ""
echo "Hyperlink.OnTapped:"
grep -n "OnTapped" /app/widget/hyperlink.go | head -5
echo ""
echo "Entry.SetMinRowsVisible:"
grep -n "SetMinRowsVisible" /app/widget/entry.go | head -3
echo ""
echo "NewAllStrings validator:"
ls -la /app/data/validation/strings.go /app/data/validation/all.go 2>&1
