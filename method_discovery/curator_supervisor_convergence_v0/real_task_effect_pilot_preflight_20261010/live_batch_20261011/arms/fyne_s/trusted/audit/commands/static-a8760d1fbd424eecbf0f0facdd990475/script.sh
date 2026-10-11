
# Check key behavioral requirements
echo "=== 1. Set() method - should implement Sscanf parsing ==="
grep -A 30 "func.*Set.*string.*error" /app/data/binding/sprintf.go | head -35

echo ""
echo "=== 2. StringToStringWithFormat - should check format == '%s' ==="
grep -B 3 -A 10 "func StringToStringWithFormat" /app/data/binding/sprintf.go

echo ""
echo "=== 3. Type switches for DataItem support ==="
grep -n "switch.*type" /app/data/binding/sprintf.go
