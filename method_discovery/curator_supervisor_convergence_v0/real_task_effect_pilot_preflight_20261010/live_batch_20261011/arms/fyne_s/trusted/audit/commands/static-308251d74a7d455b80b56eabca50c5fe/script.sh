
# Verify the parsing logic now writes to separate maps
echo "=== Color parsing sections - should write to different maps ==="
grep -A 8 "Parse colors (generic)" /app/theme/json.go | head -12
echo ""
grep -A 8 "Parse colors-dark" /app/theme/json.go | head -12
echo ""
grep -A 8 "Parse colors-light" /app/theme/json.go | head -12
