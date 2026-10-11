
cd /app
# Find ALL implementations of App interface
echo "=== All types implementing App interface ==="
grep -r "type.*App struct" --include="*.go" | grep -v "test_test.go"
echo ""
echo "=== Checking for Metadata method implementations ==="
grep -r "func.*Metadata.*AppMetadata" --include="*.go" -A 2
