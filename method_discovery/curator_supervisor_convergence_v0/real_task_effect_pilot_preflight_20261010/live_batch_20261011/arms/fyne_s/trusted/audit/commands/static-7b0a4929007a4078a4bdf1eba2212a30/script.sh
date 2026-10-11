
# Check if jsonTheme struct has been updated with separate color maps
echo "=== Current jsonTheme struct definition ==="
grep -A 12 "type jsonTheme struct" /app/theme/json.go

echo ""
echo "=== Color() method - check if it now uses variant parameter ==="
grep -A 20 "func.*Color.*ThemeColorName.*ThemeVariant" /app/theme/json.go | head -25
