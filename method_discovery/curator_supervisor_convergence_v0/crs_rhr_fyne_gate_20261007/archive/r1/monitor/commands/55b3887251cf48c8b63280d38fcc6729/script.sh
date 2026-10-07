
# Check if theme/json.go exists and has the required functions
ls -la /app/theme/json.go 2>&1
echo ""
grep -n "func FromJSON\|func FromJSONReader" /app/theme/json.go 2>&1 | head -5
