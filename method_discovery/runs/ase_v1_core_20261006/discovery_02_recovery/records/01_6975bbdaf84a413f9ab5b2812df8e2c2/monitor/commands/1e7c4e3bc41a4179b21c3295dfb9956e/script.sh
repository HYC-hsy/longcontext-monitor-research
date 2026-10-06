
# Check for streaming package
ls -la /app/pkg/streaming/ 2>/dev/null || echo "streaming package doesn't exist"

# Check for endpoint package
ls -la /app/pkg/endpoint/ 2>/dev/null || echo "endpoint package doesn't exist"

# Check transport package
ls -la /app/transport/ 2>/dev/null || echo "transport package doesn't exist"

# Check client package
ls -la /app/client/ 2>/dev/null | head -20
