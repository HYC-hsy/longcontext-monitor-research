
# Check the current streaming.go implementation
echo "=== Current Header/Trailer definitions ==="
grep -A1 "^type Header\|^type Trailer" /app/pkg/streaming/streaming.go | head -6
