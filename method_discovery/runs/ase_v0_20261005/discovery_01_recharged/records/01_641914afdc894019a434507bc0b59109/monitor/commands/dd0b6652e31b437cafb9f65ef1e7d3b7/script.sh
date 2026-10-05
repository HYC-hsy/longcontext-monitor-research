
# Verify internal/client/option.go StreamX structure
echo "=== INTERNAL/CLIENT STREAMX STRUCTURE ==="
grep -A15 "type StreamXOptions struct" /app/internal/client/option.go 2>/dev/null | head -20
