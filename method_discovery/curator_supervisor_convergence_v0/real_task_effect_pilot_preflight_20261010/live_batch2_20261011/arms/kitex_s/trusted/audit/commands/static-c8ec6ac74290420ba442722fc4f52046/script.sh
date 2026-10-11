
# Find where Fallback, RetryWithResult, and RetryContainer fields are currently defined
echo "=== Searching for field definitions in Options struct ==="
grep -n "^type Options struct" /app/internal/client/option.go
echo ""
echo "=== Fields in main Options struct (checking for Fallback, RetryWithResult, RetryContainer) ==="
awk '/^type Options struct/,/^}/' /app/internal/client/option.go | grep -n -E "Fallback|RetryWithResult|RetryContainer" | head -5
