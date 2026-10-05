
# Check internal/client StreamXOptions - did it get reverted?
echo "=== INTERNAL/CLIENT STREAMXOPTIONS CURRENT STATE ==="
grep -A10 "type StreamXOptions struct" /app/internal/client/option.go
