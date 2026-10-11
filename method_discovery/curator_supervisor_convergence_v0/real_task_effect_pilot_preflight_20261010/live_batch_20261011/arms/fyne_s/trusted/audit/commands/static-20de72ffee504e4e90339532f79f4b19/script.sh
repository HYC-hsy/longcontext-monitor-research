
# Check the jsonTheme struct definition and Color() method
echo "=== jsonTheme struct definition ==="
grep -A 10 "type jsonTheme struct" /app/theme/json.go

echo ""
echo "=== Color() method implementation ==="
grep -A 15 "func.*Color.*ThemeColorName.*ThemeVariant" /app/theme/json.go
