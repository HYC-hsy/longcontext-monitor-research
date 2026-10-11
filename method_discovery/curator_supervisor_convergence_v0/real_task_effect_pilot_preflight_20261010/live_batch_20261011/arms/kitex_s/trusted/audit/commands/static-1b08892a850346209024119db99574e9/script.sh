# Check if the required internal/client types exist
ls -la /app/internal/client/*.go | head -10
echo ""
echo "=== Checking for internal/client option types ==="
grep -n "type UnaryOption\|type StreamOption\|type TTHeaderStreamingOption" /app/internal/client/*.go 2>/dev/null || echo "Internal option types NOT FOUND"
