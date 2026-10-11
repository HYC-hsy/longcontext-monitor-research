
# Check how Colors-dark and Colors-light are actually parsed in FromJSONReader
echo "=== Checking color parsing logic in FromJSONReader ==="
grep -n "colors" /app/theme/json.go | head -20
echo ""
echo "=== Showing actual parsing code for colors sections ==="
sed -n '130,165p' /app/theme/json.go
