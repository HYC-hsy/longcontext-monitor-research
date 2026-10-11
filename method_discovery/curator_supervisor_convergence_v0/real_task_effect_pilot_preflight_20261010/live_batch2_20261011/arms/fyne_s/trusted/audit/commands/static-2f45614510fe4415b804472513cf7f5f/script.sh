
# Verify Target 2 JSON theme functions exist
echo "=== Target 2: JSON Theme Support ==="
echo "FromJSON function:"
grep -A 3 "^func FromJSON" /app/theme/json.go | head -5

echo ""
echo "FromJSONReader function:"
grep -A 3 "^func FromJSONReader" /app/theme/json.go | head -5

echo ""
echo "parseHexColor function (for 3,4,6,8 digit hex):"
grep -A 2 "^func parseHexColor" /app/theme/json.go | head -5
