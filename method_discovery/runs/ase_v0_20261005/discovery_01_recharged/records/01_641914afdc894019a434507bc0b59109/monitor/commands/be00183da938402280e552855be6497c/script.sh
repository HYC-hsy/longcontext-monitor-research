
# Check if TailOption function exists in option.go
echo "=== TailOption Function Check ==="
grep -A5 "^func TailOption" /app/client/option.go || echo "TailOption function NOT FOUND in option.go"
echo ""
# Check if retry migration has been done
echo "=== Retry Migration Check ==="
echo "Checking WithFailureRetry implementation:"
grep -A8 "func WithFailureRetry" /app/client/option.go | head -10
