
# Check if minRowsVisible is referenced anywhere in MinSize calculations
grep -n "MinSize\|minRowsVisible" /app/widget/entry.go | head -20
