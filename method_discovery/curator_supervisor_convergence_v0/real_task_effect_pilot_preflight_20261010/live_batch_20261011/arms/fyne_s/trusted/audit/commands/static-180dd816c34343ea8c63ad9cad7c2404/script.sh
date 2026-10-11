
# Check current state of jsonTheme struct and Color() method
echo "=== jsonTheme struct ==="
grep -A 8 "type jsonTheme struct" /app/theme/json.go

echo ""
echo "=== Color() method ==="
grep -A 25 "func.*Color.*ThemeColorName.*ThemeVariant" /app/theme/json.go | head -30

echo ""
echo "=== Build verification ==="
cd /app && go build ./theme 2>&1 | head -15
echo "Exit code: $?"
