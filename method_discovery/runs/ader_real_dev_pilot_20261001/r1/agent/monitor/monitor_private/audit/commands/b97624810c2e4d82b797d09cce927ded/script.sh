
cd /app
# Quick verification of critical methods/fields
echo "=== Key implementations spot check ==="
grep -n "SetMinRowsVisible" widget/entry.go | head -2
grep -n "OnTapped.*func()" widget/hyperlink.go | head -1
grep -n "func.*RemoveAll" container.go | head -1
grep -n "Icon.*Resource" menu.go | grep MenuItem | head -1
