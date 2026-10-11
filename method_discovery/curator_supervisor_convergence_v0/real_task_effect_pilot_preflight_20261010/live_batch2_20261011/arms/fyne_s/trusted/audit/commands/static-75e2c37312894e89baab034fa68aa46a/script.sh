
# Find the actual workspace location
echo "=== Locating workspace ==="
pwd
ls -la | head -20
echo ""
echo "=== Checking for Go source structure ==="
find . -name "sprintf.go" -type f 2>/dev/null | head -5
find . -name "app.go" -path "*/driver/desktop/*" -type f 2>/dev/null | head -5
