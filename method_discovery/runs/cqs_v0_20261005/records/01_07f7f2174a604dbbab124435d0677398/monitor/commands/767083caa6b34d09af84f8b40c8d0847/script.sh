
# Check Entry.SetMinRowsVisible implementation
echo "=== Checking SetMinRowsVisible method ==="
grep -n "func (e \*Entry) SetMinRowsVisible" /app/widget/entry.go

echo -e "\n=== Checking minRowsVisible field ==="
grep -n "minRowsVisible" /app/widget/entry.go | head -5
