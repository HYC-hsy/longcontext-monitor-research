
# Check if parseHexColor now has all 4 hex format cases
echo "=== parseHexColor switch cases ===" 
grep -A 50 "func parseHexColor" /app/theme/json.go | grep -E "case [0-9]:|default:"
