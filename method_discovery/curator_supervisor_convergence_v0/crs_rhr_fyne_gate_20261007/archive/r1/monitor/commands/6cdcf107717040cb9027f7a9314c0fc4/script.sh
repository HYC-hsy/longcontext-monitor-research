
# Check if data/binding/sprintf.go exists and has the required functions
ls -la /app/data/binding/sprintf.go 2>&1
echo ""
grep -n "func NewSprintf\|func StringToStringWithFormat" /app/data/binding/sprintf.go 2>&1 | head -5
