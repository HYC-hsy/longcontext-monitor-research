
# Check if the Color() method now compiles correctly
echo "=== Current Color() method ==="
grep -A 25 "func.*Color.*ThemeColorName.*ThemeVariant" /app/theme/json.go | head -30

echo ""
echo "=== Build verification ==="
cd /app && go build ./theme 2>&1
echo "Exit code: $?"
