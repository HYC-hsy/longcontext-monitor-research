
# Check if data/validation/all.go exists
ls -la /app/data/validation/all.go 2>&1
echo ""
grep -n "func NewAllStrings" /app/data/validation/all.go 2>&1 | head -5
